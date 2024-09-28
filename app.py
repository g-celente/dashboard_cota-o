from flask import Flask, render_template, request, send_file, redirect
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime
import requests
import os
import json

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
        periodo = request.form['periodo']
        carteira = request.form['carteira'] 
        intervalo = request.form['interval']

        # Definindo a URL da API BrAPI
        token = "rp7gP3CGdGZrFHJukCEQcx"
        url = f"https://brapi.dev/api/quote/{ativo}?range={periodo}&interval={intervalo}"

        # Fazendo a requisição à nova API
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        data = response.json()
        print(data)

        if 'results' not in data or not data['results']:
            error = "Ativo não encontrado ou erro na API."
            return render_template('index.html', error=error, ativo=ativo, carteiras=carteiras, retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

        # Transformando os dados recebidos em um DataFrame
        df = pd.DataFrame(data['results'][0]['historicalDataPrice'])

        # Convertendo a coluna de data e configurando o índice
        df['date'] = pd.to_datetime(df['date'], unit='s')
        df.set_index('date', inplace=True)

        # Renomeando colunas
        df.rename(columns={'close': 'fechamento'}, inplace=True)

        if df.empty:
            error = "Nenhum dado encontrado para as datas especificadas."
            return render_template('index.html', error=error, ativo=ativo, carteiras=carteiras, retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

        df['variacao'] = df['fechamento'].pct_change() * 100

        # Calcular os dados necessários
        retorno_esperado = df['variacao'].mean()
        desvio_padrao = df['variacao'].std()
        indice_desempenho = retorno_esperado / desvio_padrao if desvio_padrao != 0 else None

        store_in_db(ativo, df, carteira) 

        fig_closing = px.line(df, x=df.index, y='fechamento', title=f'Preços de Fechamento de {ativo}')
        graph_closing_html = fig_closing.to_html(full_html=False)

        fig_variation = px.line(df, x=df.index, y='variacao', title=f'Variação Percentual de {ativo}')
        graph_variation_html = fig_variation.to_html(full_html=False)

        df_html = df[['fechamento', 'variacao']].to_html()

    return render_template('index.html', graph_closing=graph_closing_html, graph_variation=graph_variation_html, ativo=ativo, df=df_html, error=error, carteiras=carteiras,
                           retorno_esperado=retorno_esperado, desvio_padrao=desvio_padrao, indice_desempenho=indice_desempenho)

def store_in_db(ativo, df, carteira):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    for index, row in df.iterrows():
        cursor.execute('''
            INSERT INTO portfolio (ativo, data, preco_fechamento, data_armazenada, nome_carteira) VALUES (?, ?, ?, ?, ?)
        ''', (ativo, index.date(), row['fechamento'], datetime.now().date(), carteira))  
    conn.commit()
    conn.close()

@app.route('/export', methods=['POST'])
def export():
    carteira_exportar = request.form['carteira_exportar']  
    conn = sqlite3.connect('database.db')


    df = pd.read_sql_query("SELECT * FROM portfolio WHERE nome_carteira=?", conn, params=(carteira_exportar,))
    conn.close()

    if df.empty:
        return "Nenhum dado encontrado para a carteira especificada.", 404  


    df_pivot = df.pivot_table(index='data', columns='ativo', values='preco_fechamento').reset_index()


    df_variations = df_pivot.set_index('data').pct_change() * 100
    df_variations.reset_index(inplace=True)


    output = f'{carteira_exportar}_report.xlsx'  
    with pd.ExcelWriter(output) as writer:

        df_pivot.to_excel(writer, index=False, sheet_name='Precos_Fechamento')
        
        df_variations.to_excel(writer, index=False, sheet_name='Variacoes_Percentuais')

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
