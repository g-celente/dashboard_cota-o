import requests
import pandas as pd

# Define o token
token = "rp7gP3CGdGZrFHJukCEQcx"

# Define o cabeçalho com o Bearer Token
headers = {
    "Authorization": f"Bearer {token}"
}

# URL da API
url_petr4 = "https://brapi.dev/api/quote/PETR4?range=5d&interval=1d"

# Fazendo a requisição com o cabeçalho
response_petr4 = requests.get(url_petr4, headers=headers)
data_petr4 = response_petr4.json()

# Verifica se há resultados
if 'results' in data_petr4 and data_petr4['results']:
    pet_data = data_petr4['results'][0]
    
    # Obtendo o preço atual e a data do último fechamento
    preco_atual = pet_data['regularMarketPrice']
    data_fechamento = pet_data['regularMarketTime']
    
    # Exibindo os dados desejados
    print("Preço Atual: R$", preco_atual)
    print("Data do Último Fechamento:", data_fechamento)
else:
    print("Nenhum dado disponível.")
