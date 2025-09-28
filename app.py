# app.py - Identificação de Pullbacks na SMA 20 | Gráficos Heikin Ashi
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# === Estilização do painel com tema escuro personalizado ===
st.markdown("""
    <style>
        body {
            background-color: #0e0e0e;
            color: white;
            font-family: 'Arial', sans-serif;
        }
        .popup-box {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 350px;
            padding: 20px;
            border-radius: 12px;
            background: rgba(0, 0, 51, 0.9);
            color: #00ffcc;
            font-weight: bold;
            z-index: 9999;
            box-shadow: 0 0 20px #00ffcc;
            animation: slideIn 0.6s ease-in-out, blinker-dourado 1.5s infinite;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes blinker-dourado {
            0%   { background-color: rgba(0, 0, 51, 0.9); }
            50%  { background-color: rgba(0, 0, 51, 0.7); }
            100% { background-color: rgba(0, 0, 51, 0.9); }
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-top: 30px;
        }
        .ativo-card {
            background: rgba(0, 0, 51, 0.8);
            border: 2px solid #00ffcc;
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            box-shadow: 0 0 10px rgba(0, 255, 204, 0.5);
        }
        .ativo-card:hover {
            transform: scale(1.02);
            box-shadow: 0 0 20px #00ffcc;
        }
        .ativo-card.alta {
            border-color: lime;
            box-shadow: 0 0 10px lime;
        }
        .ativo-card.baixa {
            border-color: red;
            box-shadow: 0 0 10px red;
        }
        .card-title {
            font-size: 20px;
            font-weight: bold;
            color: #00ffcc;
        }
        .card-price {
            font-size: 18px;
            margin-top: 10px;
            color: #ffffff;
        }
        .card-trend {
            font-size: 16px;
            margin-top: 10px;
            color: lime;
        }
        .card-trend.baixa {
            color: red;
        }
    </style>
""", unsafe_allow_html=True)

# === Função pra calcular Heikin Ashi ===
def calculate_heikin_ashi(df):
    if df.empty or 'Open' not in df.columns or 'Close' not in df.columns:
        return pd.DataFrame()
    df = df.copy()
    df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4
    df['HA_Open'] = np.nan
    for i in range(len(df)):
        if i == 0:
            df.loc[df.index[i], 'HA_Open'] = (
                df.loc[df.index[i], 'Open'] + df.loc[df.index[i], 'Close']
            ) / 2
        else:
            df.loc[df.index[i], 'HA_Open'] = (
                df.loc[df.index[i - 1], 'HA_Open'] +
                df.loc[df.index[i - 1], 'HA_Close']
            ) / 2
    df['HA_High'] = df[['High', 'HA_Open', 'HA_Close']].max(axis=1)
    df['HA_Low'] = df[['Low', 'HA_Open', 'HA_Close']].min(axis=1)
    return df

# === Função pra buscar dados via Yahoo Finance ===
def fetch_data(symbol, period='5d', interval='4h'):
    df = yf.download(tickers=symbol, period=period, interval=interval)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    df.columns = df.columns.str.lower().str.replace(' ', '_')
    df.rename(columns={'open': 'Open', 'high': 'High',
                       'low': 'Low', 'close': 'Close'}, inplace=True)
    return df

# === Função pra detectar tendência com base nas médias ===
def detect_trend(df):
    if df.empty or 'Close' not in df.columns:
        return df
    df['SMA_9'] = df['Close'].rolling(window=9).mean()
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['trend'] = np.where(df['SMA_9'] > df['SMA_20'], 'alta',
                           np.where(df['SMA_9'] < df['SMA_20'], 'baixa', None))
    return df

# === Função pra identificar cruzamento real de médias ===
def detect_crossover(df):
    if len(df) < 2 or 'SMA_9' not in df.columns or 'SMA_20' not in df.columns:
        return {'type': None}
    prev_row = df.iloc[-2]
    curr_row = df.iloc[-1]
    if prev_row['SMA_9'] < prev_row['SMA_20'] and curr_row['SMA_9'] > curr_row['SMA_20']:
        return {'type': '🟢 Cruzamento de Médias - Alta Clara'}
    elif prev_row['SMA_9'] > prev_row['SMA_20'] and curr_row['SMA_9'] < curr_row['SMA_20']:
        return {'type': '🔴 Cruzamento de Médias - Baixa Clara'}
    return {'type': None}

# === Função pra verificar posição do preço em relação à SMA 20 ===
def check_price_position_sma_20(df):
    if df.empty or 'Close' not in df.columns or 'SMA_20' not in df.columns:
        return {'position': None}
    latest = df.iloc[-1]
    if latest['Close'] > latest['SMA_20']:
        return {'position': '🟢 Preço ACIMA da SMA 20'}
    elif latest['Close'] < latest['SMA_20']:
        return {'position': '🔴 Preço ABAIXO da SMA 20'}
    return {'position': None}

# === Função pra detectar pullbacks na SMA 20 ===
def detect_pullback(df):
    if df.empty or 'Close' not in df.columns or 'SMA_20' not in df.columns:
        return {'pullback': False}
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    # Detecta pullback: preço toca ou cruza a SMA 20
    if (prev['Close'] > prev['SMA_20'] and latest['Close'] <= latest['SMA_20']) or \
       (prev['Close'] < prev['SMA_20'] and latest['Close'] >= latest['SMA_20']):
        return {'pullback': True, 'price': latest['Close']}
    return {'pullback': False}

# === Inicialização do Session State ===
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

# === Lista completa de ativos ===
symbols_full = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "USDJPY=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "GER30": "^GDAXI",
    "Ouro (GC=F)": "GC=F",
    "Prata (SI=F)": "SI=F",
    "Cripto - BTC/USD": "BTC-USD"
}

# === Mostrar header estilizado ===
st.markdown('<h1 style="text-align:center; color:#00ffcc;">🡳 Painel Traider - Gráficos + Pop-ups</h1>', unsafe_allow_html=True)

# === Inicia layout em grade com 3 colunas ===
st.markdown('<div class="grid-container">', unsafe_allow_html=True)

# === Loop principal do painel ===
for name, symbol in symbols_full.items():
    # Busca dados de 1 hora e diário
    df_1h = fetch_data(symbol, period='5d', interval='1h')
    df_daily = fetch_data(symbol, period='1mo', interval='1d')

    # Calcula Heikin Ashi e detecta tendências
    df_1h = calculate_heikin_ashi(df_1h)
    df_daily = calculate_heikin_ashi(df_daily)
    df_1h = detect_trend(df_1h)
    df_daily = detect_trend(df_daily)

    if df_1h.empty or df_daily.empty:
        continue

    # Últimos dados
    latest_1h = df_1h.iloc[-1]
    latest_daily = df_daily.iloc[-1]

    # Detecta pullbacks
    pullback_1h = detect_pullback(df_1h)
    pullback_daily = detect_pullback(df_daily)

    # Alerta especial: pullback detectado
    if pullback_1h['pullback']:
        alert_message = f"🔔 ALERTA DE PULLBACK! {name} ({symbol})\n"
        alert_message += f"📈 Preço no gráfico de 1h: ${pullback_1h['price']:.5f}\n"
        alert_message += "📊 Pullback na SMA 20!"
        st.session_state.alerts.append(alert_message)

    if pullback_daily['pullback']:
        alert_message = f"🔔 ALERTA DE PULLBACK! {name} ({symbol})\n"
        alert_message += f"📈 Preço no gráfico diário: ${pullback_daily['price']:.5f}\n"
        alert_message += "📊 Pullback na SMA 20!"
        st.session_state.alerts.append(alert_message)

    # Renderiza cartão do ativo
    card_class = "ativo-card alta" if latest_1h['trend'] == 'alta' else "ativo-card baixa"
    st.markdown(f"""
        <div class="{card_class}">
            <div class="card-title">{name}</div>
            <div class="card-price">💵 Preço: ${latest_1h['Close']:.5f}</div>
            <div class="card-trend {'alta' if latest_1h['trend'] == 'alta' else 'baixa'}">
                📈 Tendência: {latest_1h['trend'].upper()}
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Gráfico Heikin Ashi (1h)
    fig_1h = go.Figure()
    fig_1h.add_trace(go.Candlestick(
        x=df_1h['date'] if 'date' in df_1h.columns else df_1h.index,
        open=df_1h['HA_Open'],
        high=df_1h['HA_High'],
        low=df_1h['HA_Low'],
        close=df_1h['HA_Close'],
        increasing_line_color='lime',
        decreasing_line_color='red'
    ))
    fig_1h.add_trace(go.Scatter(
        x=df_1h['date'] if 'date' in df_1h.columns else df_1h.index,
        y=df_1h['SMA_9'],
        mode='lines',
        name='SMA 9',
        line=dict(color='cyan', width=1)
    ))
    fig_1h.add_trace(go.Scatter(
        x=df_1h['date'] if 'date' in df_1h.columns else df_1h.index,
        y=df_1h['SMA_20'],
        mode='lines',
        name='SMA 20',
        line=dict(color='orange', width=1)
    ))
    fig_1h.update_layout(
        title=f"{name} - Gráfico Heikin Ashi (1h)",
        xaxis_title="Data",
        yaxis_title="Preço",
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=400
    )
    st.plotly_chart(fig_1h, use_container_width=True)

    # Gráfico Heikin Ashi (diário)
    fig_daily = go.Figure()
    fig_daily.add_trace(go.Candlestick(
        x=df_daily['date'] if 'date' in df_daily.columns else df_daily.index,
        open=df_daily['HA_Open'],
        high=df_daily['HA_High'],
        low=df_daily['HA_Low'],
        close=df_daily['HA_Close'],
        increasing_line_color='lime',
        decreasing_line_color='red'
    ))
    fig_daily.add_trace(go.Scatter(
        x=df_daily['date'] if 'date' in df_daily.columns else df_daily.index,
        y=df_daily['SMA_9'],
        mode='lines',
        name='SMA 9',
        line=dict(color='cyan', width=1)
    ))
    fig_daily.add_trace(go.Scatter(
        x=df_daily['date'] if 'date' in df_daily.columns else df_daily.index,
        y=df_daily['SMA_20'],
        mode='lines',
        name='SMA 20',
        line=dict(color='orange', width=1)
    ))
    fig_daily.update_layout(
        title=f"{name} - Gráfico Heikin Ashi (Diário)",
        xaxis_title="Data",
        yaxis_title="Preço",
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=400
    )
    st.plotly_chart(fig_daily, use_container_width=True)

# === Exibe pop-ups de alertas especiais ===
for alert in st.session_state.alerts:
    st.markdown(f"""
        <div class="popup-box">
            <strong>&#9888; ALERTA!</strong>
            <br><br>
            {alert}
        </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)