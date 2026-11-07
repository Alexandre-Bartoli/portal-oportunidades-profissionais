# Estudo técnico de soluções existentes

## Projetos consultados

1. [Job Pindorama, Rosana Pêgas Godoy](https://github.com/rosanapegasgodoy/job-pindorama): adaptação brasileira com conectores locais, painel e verificação de anúncios.
2. [AI Job Search, Mads Lorentzen e colaboradores](https://github.com/ai-job-search-dev/ai-job-search): fluxo individual de busca, deduplicação, avaliação de oportunidades e segurança de texto não confiável.

Ambos divulgam licença MIT nos respectivos repositórios. Consultar sempre a licença da versão específica antes de reutilizar código de terceiros. Esta evolução utiliza uma **implementação independente em Python**, inspirada nos conceitos e nas interfaces publicamente documentadas; não inclui o código TypeScript ou os agentes dos projetos externos.

## Decisões de arquitetura

* Manter um portal web multiusuário, sem Claude Code e sem assinatura obrigatória de IA.
* Primeiro adaptador brasileiro experimental: Gupy, com filtros por tipo de contrato e paginação limitada.
* Não tratar a existência de uma rota pública como consentimento para redistribuição em escala.
* Não fazer autenticação automática, contornar bloqueios ou capturar dados dos candidatos.
* Interpretar os sinais de inconsistência como **alertas**, jamais vereditos de fraude ou elegibilidade.
* Os conectores não devem ser ativados sem revisão das condições de uso, teste manual e medição de cobertura.

## O que está implementado

* Módulo `gupy.py`, com gerador de consultas e validação de campos e URLs.
* Categorias `internship`, `employment`, `temporary`, baseadas em códigos de contrato quando disponíveis.
* Módulo `signals.py`, que alerta sobre seleção interna, pedido de pagamento e contradição entre rótulo remoto e descrição.
* Filtro de categoria no endpoint `/api/jobs` e na interface HTML.
* Testes simulados de classificação, resposta inválida, URL imprópria e sinais.

## O que NÃO foi comprovado

* Retorno de vagas reais pela Gupy no nosso ambiente.
* Autorização para coleta, conservação ou redistribuição das informações da Gupy em portal público.
* Compatibilidade do esquema externo em períodos futuros.
* Cobertura nacional de todos os cursos ou preenchimento dos filtros geográficos planejados.

## Próxima validação necessária

1. Validar condições legais e técnicas de consulta ao provedor.
2. Consultar a rota pública em ambiente de rede e registrar status, esquema e limites.
3. Confirmar URLs oficiais de candidatura e não substituir metadados ausentes por inferências.
4. Habilitar seletivamente uma fonte e verificar resultados antes de ampliar a frequência.
5. Medir taxa de vagas válidas por curso e estado.