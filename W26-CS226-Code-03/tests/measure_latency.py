"""
End-to-End Latency Measurement Tool
-------------------------------------
Calculates pipeline latency: fire event creation time vs. DuckDB ingestion time.
Uses the shared _get_connection so it benefits from the retry/lock logic and
does not conflict with any running consumer process.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alert_sink.duckdb_store import _get_connection, DB_PATH_SIM

MAX_WAIT_S = 60   # wait up to 60 seconds for the consumer to release the lock

def main():
    if not os.path.exists(DB_PATH_SIM):
        print(f"Error: Database not found at {DB_PATH_SIM}")
        return

    print("Attempting to connect (will retry up to 60s if consumer holds the lock)...")
    
    con = None
    deadline = time.time() + MAX_WAIT_S
    while time.time() < deadline:
        try:
            # _get_connection already has its own retry, but since it's RW we try here
            con = _get_connection(read_only=False, db_path=DB_PATH_SIM)
            break
        except Exception as e:
            if time.time() >= deadline:
                print(f"Timed out waiting for DB lock: {e}")
                return
            print(f"  DB locked, retrying in 2s... ({e})")
            time.sleep(2)

    if con is None:
        print("Could not connect.")
        return

    try:
        query = """
            SELECT
                event_id,
                building_name,
                event_time,
                ingestion_ts,
                date_diff('millisecond',
                    CAST(event_time AS TIMESTAMP),
                    CAST(ingestion_ts AS TIMESTAMP)
                ) AS latency_ms
            FROM alerts_live
            WHERE ingestion_ts IS NOT NULL
              AND event_time IS NOT NULL
            ORDER BY ingestion_ts DESC
            LIMIT 1000
        """

        df = con.execute(query).df()

        if df.empty:
            print("No alerts in the DB yet. Run populate_for_latency_test.py first.")
            return

        # Filter out negative latencies (clock skew / test inserts with old timestamps)
        df = df[df['latency_ms'] >= 0]

        avg_latency = df['latency_ms'].mean() / 1000.0
        max_latency = df['latency_ms'].max() / 1000.0
        min_latency = df['latency_ms'].min() / 1000.0
        p95_latency = df['latency_ms'].quantile(0.95) / 1000.0

        print("\n" + "="*55)
        print("  PIPELINE LATENCY REPORT (Last 1000 Alerts)")
        print("="*55)
        print(f"  Total Evaluated : {len(df):,} alerts")
        print(f"  Average Latency : {avg_latency:.2f}s")
        print(f"  P95 Latency     : {p95_latency:.2f}s")
        print(f"  Min Latency     : {min_latency:.2f}s")
        print(f"  Max Latency     : {max_latency:.2f}s")
        print("="*55)

        if avg_latency < 30.0:
            print(f"\n  SUCCESS: Average {avg_latency:.2f}s meets the <30s SLA!")
        else:
            print(f"\n  WARN: {avg_latency:.2f}s exceeds 30s SLA. Scale Spark executors.")

        # --- Generate High-Quality Chart for Report ---
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            import seaborn as sns

            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            fig.suptitle("End-to-End Pipeline Latency Analysis", fontsize=16, fontweight='bold')

            # Left: histogram + KDE
            ax1 = axes[0]
            sns.histplot(df['latency_ms'] / 1000.0, bins=30, kde=True, color='#6c5ce7', ax=ax1)
            ax1.axvline(avg_latency, color='#e17055', linestyle='--', linewidth=2,
                        label=f'Average: {avg_latency:.2f}s')
            ax1.axvline(p95_latency, color='#fdcb6e', linestyle='--', linewidth=2,
                        label=f'P95: {p95_latency:.2f}s')
            ax1.axvline(30.0, color='#d63031', linestyle=':', linewidth=2,
                        label='SLA Target: 30s')
            ax1.set_xlabel('Latency (seconds)', fontsize=12)
            ax1.set_ylabel('Number of Events', fontsize=12)
            ax1.set_title('Latency Distribution', fontsize=13)
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Right: CDF
            ax2 = axes[1]
            sorted_lat = df['latency_ms'].sort_values() / 1000.0
            cdf = [i / len(sorted_lat) for i in range(len(sorted_lat))]
            ax2.plot(sorted_lat, cdf, color='#00b894', linewidth=2)
            ax2.axvline(30.0, color='#d63031', linestyle=':', linewidth=2, label='30s SLA')
            ax2.axhline(0.95, color='#fdcb6e', linestyle='--', linewidth=1.5, label='P95 line')
            ax2.set_xlabel('Latency (seconds)', fontsize=12)
            ax2.set_ylabel('CDF (% of events)', fontsize=12)
            ax2.set_title('Cumulative Latency Distribution', fontsize=13)
            ax2.legend()
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            chart_path = os.path.join(os.path.dirname(__file__), 'latency_distribution.png')
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            print(f"\n  Chart saved: {chart_path}")

        except ImportError:
            print("  (Install matplotlib+seaborn to generate chart)")

    except Exception as e:
        print(f"Query failed: {e}")
        import traceback; traceback.print_exc()
    finally:
        if con:
            con.close()

if __name__ == "__main__":
    main()
