import io
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)

def generate_chart_with_levels(ticker: str, entry: float = None, tp: float = None, sl: float = None) -> bytes | None:
    """
    Downloads historical data for the ticker and generates a candlestick chart
    using mplfinance with horizontal lines for Entry, Take Profit, and Stop Loss.
    Returns the chart image as PNG bytes.
    """
    try:
        import matplotlib
        matplotlib.use('Agg') # Ensure headless rendering on server
        import yfinance as yf
        import pandas as pd
        import mplfinance as mpf
    except ImportError:
        logger.warning("mplfinance or yfinance not installed — skipping chart generation.")
        return None

    try:
        # Fetch 6 months of historical data
        end_date = datetime.now()
        start_date = end_date - relativedelta(months=6)
        
        # Clean ticker for yfinance if it has special characters (though yf handles most)
        clean_ticker = ticker.split(" ")[0].strip()
        
        df = yf.download(clean_ticker, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
        
        # Fix yfinance returning MultiIndex in newer versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        if df.empty:
            logger.warning(f"No data found for ticker {ticker} to draw chart.")
            return None
            
        # Determine lines to draw
        lines = []
        colors = []
        
        if tp is not None:
            lines.append(float(tp))
            colors.append('g') # Green for Take Profit
            
        if entry is not None:
            lines.append(float(entry))
            colors.append('b') # Blue for Entry
            
        if sl is not None:
            lines.append(float(sl))
            colors.append('r') # Red for Stop Loss
            
        # Configure hlines if any levels were provided
        hlines = dict(hlines=lines, colors=colors, linestyle='--', linewidths=1.5, alpha=0.7) if lines else None

        # Setup plotting kwargs
        kwargs = dict(
            type='candle',
            style='yahoo',
            volume=False,
            title=f"{ticker} - 6 Month Analysis",
            ylabel='Price',
            figsize=(10, 6),
            tight_layout=True,
            returnfig=True
        )
        
        if hlines:
            kwargs['hlines'] = hlines

        # Generate plot
        fig, axes = mpf.plot(df, **kwargs)
        
        # Add labels to lines if possible
        if hlines and axes:
            ax = axes[0]
            # Stagger text x-positions to avoid horizontal overlap when prices are very close
            x_pos_tp = max(0, len(df) - 8)
            x_pos_entry = max(0, len(df) - 20)
            x_pos_sl = max(0, len(df) - 32)
            
            bbox_style = dict(facecolor='white', alpha=0.85, edgecolor='none', pad=3)
            if tp is not None:
                ax.text(x_pos_tp, float(tp), ' TP ', color='green', verticalalignment='bottom', horizontalalignment='right', fontsize=10, fontweight='bold', bbox=bbox_style)
            if entry is not None:
                ax.text(x_pos_entry, float(entry), ' Entry ', color='blue', verticalalignment='bottom', horizontalalignment='right', fontsize=10, fontweight='bold', bbox=bbox_style)
            if sl is not None:
                ax.text(x_pos_sl, float(sl), ' SL ', color='red', verticalalignment='top', horizontalalignment='right', fontsize=10, fontweight='bold', bbox=bbox_style)

        # Save to bytes buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120)
        buf.seek(0)
        
        # Free memory
        import matplotlib.pyplot as plt
        plt.close(fig)
        
        return buf.getvalue()
        
    except Exception as e:
        logger.error(f"Failed to generate chart for {ticker}: {e}")
        return None
