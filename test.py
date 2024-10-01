import requests
import pandas as pd

# Define o token
token = "2ZB7EGv55yUzUgDkPAGyDb"

# Define o cabeçalho com o Bearer Token
headers = {
    "Authorization": f"Bearer {token}"
}

# URL da API
url_petr4 = "https://brapi.dev/api/quote/PETR4?range=5y&interval=1mo&dividends=true"

response = requests.get(url_petr4)

#response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
data = response.json()

if 'results' not in data or not data['results']:
    error = "Ativo não encontrado ou erro na API."

# Transformando os dados recebidos em um DataFrame

# Verificando os dados de dividendos
dividends_data = data['dividendsData'][0].get('cashDividends', [])
print(dividends_data)  # Para depuração

if dividends_data:  # Apenas crie o DataFrame se houver dados de dividendos
    df_dividends = pd.DataFrame(dividends_data)
    
    # Convertendo a coluna de data
    df_dividends['date'] = pd.to_datetime(df_dividends['date'], unit='s')
    df_dividends.set_index('date', inplace=True)
    
    # Exibir o DataFrame de dividendos (para depuração)
    print(df_dividends)

    # Aqui você pode criar o gráfico para os dividendos
    fig_dividends = px.bar(df_dividends, x=df_dividends.index, y='value', title=f'Dividends de {ativo}')
    graph_dividends_html = fig_dividends.to_html(full_html=False)
else:
    graph_dividends_html = None  # Caso não haja dados de dividendo