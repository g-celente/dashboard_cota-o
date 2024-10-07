from flask import Flask, render_template, request, send_file, redirect
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime
import requests
import os
import json
import yfinance as yf

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            ativo TEXT,
            data DATE,
            preco_fechamento REAL,
            data_armazenada DATE,
            nome_carteira TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    graph_closing_html = None
    graph_variation_html = None
    graph_dividends_html = None  # Novo gráfico para dividendos
    error = None
    df_html = None
    ativo = None  
    retorno_esperado = None
    desvio_padrao = None
    indice_desempenho = None

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nome_carteira FROM portfolio")
    carteiras = [row[0] for row in cursor.fetchall()]  
    conn.close()

    if request.method == 'POST':
        ativo = request.form['ativo']
        periodo = request.form['periodo']  # Exemplo: "1y", "6mo", "3mo"
        intervalo = request.form['interval']  # Exemplo: "1d", "1wk", "1mo"
        carteira = request.form['carteira']

        # Baixando os dados do Yahoo Finance
        try:
            if not ativo.endswith('.SA'):
                ativo = f"{ativo}.SA"
                
            df_price = yf.download(ativo, period=periodo, interval=intervalo)

            if df_price.empty:
                error = "Nenhum dado encontrado para as datas especificadas."
                return render_template('index.html', error=error, ativo=ativo, carteiras=carteiras, retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

            # Usando a coluna 'Adj Close' para obter o preço ajustado
            df_price.rename(columns={'Adj Close': 'fechamento'}, inplace=True)

            # Calculando a variação percentual
            df_price['variacao'] = df_price['fechamento'].pct_change() * 100
            retorno_esperado = df_price['variacao'].mean()
            desvio_padrao = df_price['variacao'].std()
            indice_desempenho = retorno_esperado / desvio_padrao if desvio_padrao != 0 else None

            # Armazenando no banco de dados
            store_in_db(ativo, df_price, carteira)

            # Gerando gráficos
            fig_closing = px.line(df_price, x=df_price.index, y='fechamento', title=f'Preços Ajustados de Fechamento de {ativo}')
            graph_closing_html = fig_closing.to_html(full_html=False)

            fig_variation = px.line(df_price, x=df_price.index, y='variacao', title=f'Variação Percentual de {ativo}')
            graph_variation_html = fig_variation.to_html(full_html=False)

            df_html = df_price[['fechamento', 'variacao']].to_html()

        except Exception as e:
            error = f"Erro ao buscar dados do Yahoo Finance: {str(e)}"
            return render_template('index.html', error=error, ativo=ativo, carteiras=carteiras, retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

    return render_template('index.html', graph_closing=graph_closing_html, graph_variation=graph_variation_html, ativo=ativo, df=df_html, error=error, carteiras=carteiras,
                           retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

def store_in_db(ativo, df, carteira, peso=None):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    for index, row in df.iterrows():
        # Certifique-se de passar 6 valores para a tabela
        cursor.execute('''
            INSERT INTO portfolio (ativo, data, preco_fechamento, data_armazenada, nome_carteira) 
            VALUES (?, ?, ?, ?, ?)
        ''', (ativo, index.date(), row['fechamento'], datetime.now().date(), carteira))
    
    conn.commit()
    conn.close()



@app.route('/export', methods=['POST'])
def export():
    carteira_exportar = request.form['carteira_exportar']  
    conn = sqlite3.connect('database.db')

    # Lê a tabela do banco de dados incluindo os preços de fechamento
    df = pd.read_sql_query("SELECT ativo, data, preco_fechamento FROM portfolio WHERE nome_carteira=?", conn, params=(carteira_exportar,))
    conn.close()

    # Verifica se o dataframe está vazio
    if df.empty:
        return "Nenhum dado encontrado para a carteira especificada.", 404

    if 'BOVA11.SA' not in df['ativo'].values:
        return render_template('carteiras.html', error="O ativo BOVA11 não está presente na carteira. Por favor, insira o BOVA11 para poder exportar."), 400

    # Cria uma tabela pivot com os preços de fechamento dos ativos
    df_pivot = df.pivot_table(index='data', columns='ativo', values='preco_fechamento').reset_index()

    # Calcula as variações percentuais de cada ativo usando pct_change()
    df_variations = df_pivot.copy()
    df_variations[df_pivot.columns[1:]] = df_pivot[df_pivot.columns[1:]].pct_change()
    # Exclui a coluna 'data' ao calcular retorno esperado e desvio padrão
    df_variations_numeric = df_variations.drop(columns=['data'])

    # Reorganiza para garantir que BOVA11 esteja por último na tabela de variações percentuais
    ativos = list(df_variations_numeric.columns)
    if 'BOVA11.SA' in ativos:
        ativos.remove('BOVA11.SA')
    ativos.append('BOVA11.SA')  # Adiciona BOVA11 ao final da lista
    df_variations_numeric = df_variations_numeric[ativos]  # Reorganiza o DataFrame de variações

    # Conta a quantidade de ativos únicos
    quantidade_ativos = df['ativo'].nunique()

    # Cálculo da variação percentual de BOVA11
    bova11_variations = df_variations_numeric['BOVA11.SA']

    media_bova11 = bova11_variations.mean()
    variancia_bova112 = (1 / len(bova11_variations)) * ((bova11_variations - media_bova11)** 2).sum()
    variancia_bova11 = bova11_variations.var()

    # Cálculos de retorno esperado, desvio padrão e índice de desempenho para cada ativo
    retorno_esperado = df_variations_numeric.mean()
    desvio_padrao = df_variations_numeric.std()
    indice_desempenho = (retorno_esperado / desvio_padrao)
    indice_sharpe = ((retorno_esperado - 0.0088) / desvio_padrao) 

    # Cálculo do Beta para cada ativo
    beta_values = {}
    for ativo in df_variations_numeric.columns:
        if ativo != 'BOVA11.SA':
            covariacao = bova11_variations.cov(df_variations_numeric[ativo])
            # Aqui usamos a variância fixa do BOVA11
            beta = covariacao / variancia_bova11
            beta_values[ativo] = beta

    # Criar DataFrame para os Betas
    beta_series = pd.Series(beta_values, name='BETA')

    # Exclui BOVA11 para o cálculo da matriz de covariância
    df_variations_numeric_excluido = df_variations_numeric.drop(columns=['BOVA11.SA'])

    # Cálculo da matriz de covariância (sem BOVA11)
    matriz_covariancia = df_variations_numeric_excluido.cov()

    # Criar um DataFrame da matriz de covariância
    matriz_cov_df = pd.DataFrame(matriz_covariancia)

    # Atribui pesos percentuais iguais para cada ativo (sem incluir BOVA11)
    quantidade_ativos_excluido = quantidade_ativos - 1  # Um ativo a menos
    peso = (1 / quantidade_ativos_excluido)  # Peso igual para cada ativo em percentual

    # Criar um DataFrame para os indicadores de desempenho e pesos
    indicadores_df = pd.DataFrame({
        'E(R)': retorno_esperado,
        'DP': desvio_padrao,
        'Índ. de Desemp.': indice_desempenho,
        'Índ. de Sharpe': indice_sharpe,
        'Peso (%)': peso
    }).transpose()

    # Adiciona os Betas ao DataFrame de indicadores
    indicadores_df.loc['BETA'] = beta_series

    # Cálculo da matriz de covariância personalizada
    ativos = list(beta_values.keys())
    matriz_cov_custom = pd.DataFrame(index=ativos, columns=ativos)

    # Calcula a matriz de covariância com base nos betas e variância do BOVA11
    for ativo1 in ativos:
        for ativo2 in ativos:
            beta1 = beta_values[ativo1]
            beta2 = beta_values[ativo2]
            # Cálculo da covariância: Beta_ativo1 * Beta_ativo2 * Variância(BOVA11)
            covariancia = beta1 * beta2 * variancia_bova11
            matriz_cov_custom.loc[ativo1, ativo2] = covariancia

    # Nome do arquivo de saída
    output = f'{carteira_exportar}_report.xlsx'

    with pd.ExcelWriter(output) as writer:
        df_pivot.to_excel(writer, index=False, sheet_name='Precos_Fechamento')
        df_variations.to_excel(writer, index=False, sheet_name='Variacoes_Percentuais')
        indicadores_df.to_excel(writer, sheet_name='Desempenho_Ativos')
        matriz_cov_custom.to_excel(writer, sheet_name='Matriz_Covariancia_Customizada')

    return send_file(output, as_attachment=True)




@app.route('/carteiras', methods=['GET'])
def listar_carteiras():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nome_carteira FROM portfolio")
    carteiras = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template('carteiras.html', carteiras=carteiras)

@app.route('/carteiras/excluir/<carteira>', methods=['POST'])
def excluir_carteira(carteira):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM portfolio WHERE nome_carteira=?", (carteira,))
    conn.commit()
    conn.close()
    return redirect('/carteiras')



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
