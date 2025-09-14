# app.py - Trader Qwen | Pure App Edition (Sem Telegram, Só Pop-ups no iPhone)
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# === CONFIGURAÇÃO GLOBAL ===
st.set_page_config(page_title="Trader Qwen", layout="wide")

# === ESTILO DARK MODE PROFISSIONAL ===
st.markdown("""
    <style>
        body { background-color: #0e0e0e; color: white; font-family: 'Segoe UI', sans-serif; }
        .popup-box {
            position: fixed; top: 20px; right: 20px; width: 400px; padding: 20px;
            border-radius: 12px; background: rgba(15, 15, 30, 0.95);
            color: #00ffcc; z-index: 9999; box-shadow: 0 0 25px #00ffcc;
            animation: slideIn 0.6s ease-out;
            border-left: 4px solid #00ffcc;
        }
        @keyframes slideIn {
            from { transform: translateX(120%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        .grid-container {
            display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 30px;
        }
        .ativo-card {
            background: rgba(15, 15, 30, 0.8); border: 1.5px solid #333; border-radius: 12px;
            padding: 20px; transition: all 0.3s ease; box-shadow: 0 0 10px rgba(0,255,204,0.2);
        }
        .ativo-card:hover {
            transform: scale(1.02); box-shadow: 0 0 20px #00ffcc;
        }
        .ativo-card.alta { border-color: lime; box-shadow: 0 0 15px lime; }
        .ativo-card.baixa { border-color: red; box-shadow: 0 0 15px red; }
        .card-title { font-size: 19px; font-weight: bold; color: #00ffcc; margin-bottom: 8px; }
        .card-price { font-size: 17px; color: #ffffff; margin: 6px 0; }
        .card-trend { font-size: 15px; margin: 6px 0; }
        .card-trend.alta { color: lime; }
        .card-trend.baixa { color: red; }
        .alert-icon { font-size: 24px; margin-right: 8px; }
        .footer { text-align: center; margin-top: 60px; color: #777; font-size: 12px; }
        h1 { color: #00ffcc; text-align: center; margin-bottom: 10px; }
        p { color: #aaa; text-align: center; margin-bottom: 30px; }
    </style>
""", unsafe_allow_html=True)

# === FUNÇÕES ===


def calculate_heikin_ashi(df):
    if df.empty or not all(col in df.columns for col in ['Open', 'High', 'Low', 'Close']):
        return pd.DataFrame()
    df = df.copy()
    df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
    df['HA_Open'] = np.nan
    for i in range(len(df)):
        if i == 0:
            df.loc[df.index[i], 'HA_Open'] = (
                df.loc[df.index[i], 'Open'] + df.loc[df.index[i], 'Close']) / 2
        else:
            df.loc[df.index[i], 'HA_Open'] = (
                df.loc[df.index[i-1], 'HA_Open'] + df.loc[df.index[i-1], 'HA_Close']) / 2
    df['HA_High'] = df[['High', 'HA_Open', 'HA_Close']].max(axis=1)
    df['HA_Low'] = df[['Low', 'HA_Open', 'HA_Close']].min(axis=1)
    return df


def fetch_data(symbol, period='5d', interval='4h'):
    try:
        df = yf.download(tickers=symbol, period=period,
                         interval=interval, progress=False)
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.reset_index(inplace=True)
        df.columns = df.columns.str.lower().str.replace(' ', '_')
        df.rename(columns={'open': 'Open', 'high': 'High',
                  'low': 'Low', 'close': 'Close'}, inplace=True)
        if 'volume' not in df.columns:
            df['Volume'] = 0
        else:
            df['Volume'] = df['volume']
        return df
    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar {symbol}: {str(e)}")
        return pd.DataFrame()


def detect_trend_and_strength(df):
    if df.empty or len(df) < 20:
        return df
    df['SMA_9'] = df['Close'].rolling(window=9).mean()
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['ATR'] = df['High'] - df['Low']

    if df['Volume'].sum() > 0:
        df['Volume_MA'] = df['Volume'].rolling(window=10).mean()
        df['is_high_volume'] = df['Volume'] > df['Volume_MA']
    else:
        df['Volume_MA'] = 0
        df['is_high_volume'] = True

    df['trend_strength'] = ((df['SMA_9'] - df['SMA_20']) / df['SMA_20']) * 100
    df['is_strong_signal'] = (
        df['trend_strength'].abs() > 0.5) & df['is_high_volume']
    df['trend'] = np.where(df['SMA_9'] > df['SMA_20'], 'alta',
                           np.where(df['SMA_9'] < df['SMA_20'], 'baixa', None))
    return df


def detect_crossover(df):
    if len(df) < 2:
        return {'type': None}
    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]
    if prev_row['SMA_9'] < prev_row['SMA_20'] and curr_row['SMA_9'] > curr_row['SMA_20']:
        return {'type': '🟢 Cruzamento de Médias - Alta Clara'}
    elif prev_row['SMA_9'] > prev_row['SMA_20'] and curr_row['SMA_9'] < curr_row['SMA_20']:
        return {'type': '🔴 Cruzamento de Médias - Baixa Clara'}
    return {'type': None}


# === STATE ===
if 'last_trend' not in st.session_state:
    st.session_state.last_trend = {}

# === LISTA DE ATIVOS ===
symbols_full = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "USDJPY=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "NZD/USD": "NZDUSD=X",
    "CHF/USD": "CHFUSD=X",
    "GER30": "^GDAXI",
    "Ouro (GC=F)": "GC=F",
    "Prata (SI=F)": "SI=F",
    "Cripto - BTC/USD": "BTC-USD",
    "Cripto - ETH/USD": "ETH-USD"
}

# === HEADER ===
st.markdown('<h1>🚀 Trader Qwen</h1>', unsafe_allow_html=True)
st.markdown('<p>Análise Automática de Tendências — Sem Ruído. Só Sinais Reais.</p>',
            unsafe_allow_html=True)

# === GRID ===
st.markdown('<div class="grid-container">', unsafe_allow_html=True)

for name, symbol in symbols_full.items():
    df_4h = fetch_data(symbol)
    if df_4h.empty:
        continue

    df_4h = calculate_heikin_ashi(df_4h)
    df_4h = detect_trend_and_strength(df_4h)
    df_4h.dropna(subset=['trend'], inplace=True)
    if df_4h.empty:
        continue

    latest = df_4h.iloc[-1]
    trend_direction = latest['trend']
    is_strong = latest.get('is_strong_signal', False)

    # DETECTA CROSSOVER
    crossover = detect_crossover(df_4h)
    crossover_type = crossover['type']

    # POP-UP ANIMADO (SÓ SE FOR SINAL FORTE)
    if crossover_type and is_strong:
        st.markdown(f"""
            <div class="popup-box">
                <span class="alert-icon">⚡</span>
                <strong>{crossover_type}</strong><br>
                💰 Ativo: {name} ({symbol})<br>
                📈 Preço: ${latest['Close']:.5f}<br>
                📊 Força: {latest['trend_strength']:.2f}%<br>
                ⏱️ Último sinal: {datetime.now().strftime('%H:%M')}
            </div>
        """, unsafe_allow_html=True)

    # MUDANÇA DE DIREÇÃO
    last_trend = st.session_state.last_trend.get(name, None)
    current_trend = latest['trend']
    if last_trend != current_trend and last_trend is not None and is_strong:
        st.markdown(f"""
            <div class="popup-box">
                <span class="alert-icon">🔄</span>
                <strong>MUDANÇA DE DIREÇÃO — FORTE</strong><br>
                💝 Ativo: {name} ({symbol})<br>
                ❌ Anterior: {last_trend.upper()}<br>
                ✅ Novo: {current_trend.upper()}<br>
                💵 Preço: ${latest['Close']:.5f}
            </div>
        """, unsafe_allow_html=True)

    st.session_state.last_trend[name] = current_trend

    # CARD DO ATIVO
    card_class = "ativo-card alta" if latest['trend'] == 'alta' else "ativo-card baixa"
    st.markdown(f"""
        <div class="{card_class}">
            <div class="card-title">{name}</div>
            <div class="card-price">💵 Preço: ${latest['Close']:.5f}</div>
            <div class="card-trend {'alta' if latest['trend'] == 'alta' else 'baixa'}">
                📈 Tendência: {latest['trend'].upper()} {'🔥' if is_strong else ''}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # GRÁFICO HEIKIN ASHI
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df_4h['date'] if 'date' in df_4h.columns else df_4h.index,
        open=df_4h['HA_Open'],
        high=df_4h['HA_High'],
        low=df_4h['HA_Low'],
        close=df_4h['HA_Close'],
        increasing_line_color='lime',
        decreasing_line_color='red'
    ))
    fig.add_trace(go.Scatter(
        x=df_4h['date'] if 'date' in df_4h.columns else df_4h.index,
        y=df_4h['SMA_9'],
        mode='lines',
        name='SMA 9',
        line=dict(color='cyan', width=1.5)
    ))
    fig.add_trace(go.Scatter(
        x=df_4h['date'] if 'date' in df_4h.columns else df_4h.index,
        y=df_4h['SMA_20'],
        mode='lines',
        name='SMA 20',
        line=dict(color='orange', width=1.5)
    ))
    fig.update_layout(
        title=f"{name} - Heikin Ashi (4h)",
        xaxis_title="Data",
        yaxis_title="Preço",
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=380,
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown('</div>', unsafe_allow_html=True)

# === RODAPÉ ===
st.markdown("""
    <div class="footer">
        💡 Feito com Qwen3 — Design limpo. Sinais reais. Zero distração.
    </div>
""", unsafe_allow_html=True)
