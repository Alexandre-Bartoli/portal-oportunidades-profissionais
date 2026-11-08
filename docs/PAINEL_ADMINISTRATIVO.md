# Painel administrativo local

O painel de consulta está disponível em `/admin` no servidor local. Ele mostra fontes configuradas e habilitadas, resultado da última coleta por fonte, quantidades informadas, revisão documental, sugestões passivas, histórico posterior à instalação, links auditados quando houver relatório, arquivos de backup local de homologação e alertas. É somente de leitura: não ativa fontes, não altera permissões e não executa coletas ou restaurações.

## Configurar acesso

Defina as variáveis `PORTAL_ADMIN_USER` e `PORTAL_ADMIN_PASSWORD` no ambiente do processo. A senha precisa ter de 32 a 256 caracteres; gere uma senha aleatória exclusiva e mantenha-a fora do repositório, do histórico de comandos e das mensagens. Sem configuração válida, o painel responde HTTP 503. O arquivo `.env.example` é somente um exemplo: a aplicação não o carrega automaticamente.

Exemplo em um terminal Unix, usando entrada oculta para a senha escolhida:

```sh
export PORTAL_ADMIN_USER=operador
read -r -s -p 'Senha administrativa: ' PORTAL_ADMIN_PASSWORD
export PORTAL_ADMIN_PASSWORD
python3 app.py stage-serve
```

O comando de homologação exige que o banco isolado já exista. Acesse `http://127.0.0.1:8767/admin` no mesmo computador e informe as credenciais na janela do navegador. Na execução local de desenvolvimento, `python3 app.py serve` usa a porta 8766 e inicia a coleta automática; avalie as condições das fontes antes de acioná-la.

O navegador pode manter as credenciais em memória após a autenticação. Encerre a sessão do navegador ao terminar. Altere a senha no ambiente e reinicie o processo para substituí-la. Nunca coloque credenciais na URL.

## Proteções e limites

Os endpoints `/admin`, `/api/admin`, `/api/collection-status` e `/api/staging-status` exigem autenticação. O acesso usa autenticação HTTP Basic e comparação de credenciais. Cinco tentativas inválidas por endereço causam bloqueio temporário de 60 segundos. O limite existe apenas na memória do processo e é reiniciado quando ele termina. Requisições sem credenciais recebem desafio de autenticação. A interface pública de consulta permanece acessível localmente.

**Este servidor escuta apenas em loopback e não possui HTTPS. Não o exponha à internet.** HTTP Basic envia credenciais codificadas, sem criptografia própria. A operação pública exige HTTPS, arquitetura de autenticação e autorização adequada, limitação distribuída, registros de segurança, revisão de segurança e configuração de proxy apropriada. O bloqueio por endereço não deve ser considerado suficiente atrás de um proxy ou em implantação com múltiplos processos.

## Como interpretar os indicadores

Os números e estados dependem dos dados que cada coleta já registra. Quantidades ausentes aparecem como não registradas, sem serem tratadas como zero. A presença de um arquivo de backup não comprova sua integridade, sua restauração nem a existência de cópia externa. A auditoria de links é uma amostra e uma resposta HTTP não prova que a vaga ainda está aberta.

O histórico guarda no banco do respectivo ambiente somente data, modo e contagens gerais de execuções novas. Dados anteriores não são reconstruídos. Falhas ao registrar histórico são indicadas no relatório da coleta e no painel. As sugestões são exibidas somente quando o respectivo ambiente produziu o arquivo de sugestões; não há ativação automática.

Em homologação, o painel lê o relatório e os backups do diretório configurado em `PORTAL_STAGING_DIR`; no modo local, lê o estado da coleta local e identifica os backups como pertencentes à homologação. O painel não realiza monitoramento contínuo nem verifica backups externos.

Procedimentos de backup, restauração e armazenamento de homologação estão em [HOMOLOGACAO_09.md](HOMOLOGACAO_09.md). Revise as condições de uso de cada fonte antes de executá-la ou publicar os resultados.
