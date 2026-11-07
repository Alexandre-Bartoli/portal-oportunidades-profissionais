# Referências, escopo e direitos autorais

A fase atual investiga e adapta conceitos dos seguintes repositórios:

* Career Ops: https://github.com/career-ops-hq/career-ops
  * Autoria e copyright da licença consultada: Santiago Fernández de Valderrama, 2026.
  * Conceitos estudados: auditoria de conectores, estados de saúde, identificação forte de anúncios, manutenção e descoberta de quadros de vagas.
* Job Pindorama: https://github.com/rosanapegasgodoy/job-pindorama
  * Adaptação brasileira do AI Job Search. Conceitos estudados: busca em portais brasileiros, normalização de regimes de contratação, validação das respostas e deduplicação.
* AI Job Search: https://github.com/MadsLorentzen/ai-job-search
  * Conceitos estudados: busca assistida, candidatura humana supervisionada, tratamento de descrições e histórico de candidaturas.

Os repositórios consultados declaram licença MIT. O código `source_quality.py` e `listing_identity.py` foi escrito especificamente para este projeto com implementação independente dos algoritmos, e **não contém cópias diretas** dos arquivos originais. Não se atribui licença MIT ao código integral do nosso portal sem autorização do titular. Caso componentes de terceiros venham a ser copiados, deverão acompanhar seus avisos originais de licença e copyright e ter obrigações verificadas.

## Implementado nesta fase

* Validação rigorosa de `sources.json`, incluindo identificadores e configuração habilitada.
* Auditoria explícita de respostas: `ok`, `empty` e `error` com causas diferenciadas.
* Preservação de dados quando consulta falhar: apenas fonte com resposta válida pode atualizar ausências.
* Identificação forte baseada em provedor, quadro e identificador nativo.
* Normalização conservadora de URLs HTTPS e retirada de parâmetros de rastreamento para reconhecimento de duplicidades exatas.
* Treze testes unitários novos para os módulos de qualidade e identidade.

## Limites desta entrega

* A identidade `listing_v1_` é utilitário adicional. A migração dos IDs já armazenados no SQLite não foi efetuada para não criar perda de vínculo com dados existentes.
* A deduplicação entre fontes está disponível como função reutilizável, ainda não foi ligada ao banco de dados e à API. Não se deve mesclar automaticamente vagas distintas com título semelhante.
* Não se ativaram fontes novas nem se comprovou coleta externa real.
* O monitoramento de vagas encerradas continua baseado em ausência após consultas completas e bem sucedidas, não em leitura automatizada da página individual.
* A busca individual futura terá perfis e candidaturas com isolamento de dados por usuário, autorização e consentimento. Não deve ser incorporada ao protótipo público sem autenticação.