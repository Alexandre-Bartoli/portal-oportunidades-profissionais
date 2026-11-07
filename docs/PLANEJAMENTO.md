# Planejamento funcional do Portal de Oportunidades Profissionais

## Propósito

Portal web para localizar automaticamente oportunidades de **estágio**, **emprego** e **trabalho temporário** para estudantes de cursos técnicos e superiores, egressos e demais interessados, em todas as áreas de formação. Atuação nacional e internacional.

## Filtros previstos

1. **Categoria:** estágio, emprego ou vaga temporária.
2. **Abrangência:** nacional, internacional ou ambas.
3. **Brasil:** todo o país; UF; município; apenas município; todo o estado; município e arredores.
4. **Raio:** 10 a 200 km, seleção inicial em 50 km, com cálculo em linha reta usando coordenadas de municípios, sem confundir com distância rodoviária.
5. **Exterior:** país, região, cidade, idioma, elegibilidade para candidato residente no Brasil e requisitos de autorização de trabalho, quando divulgados.
6. **Geral:** cargo, área ou curso, presencial/híbrido/remoto, nível, experiência, remuneração e data, quando declarados pela fonte.

Para vagas remotas, país da empresa, localização do anúncio e países em que a pessoa pode ser contratada são informações distintas e devem ser preservadas.

## Coleta

* Conectores para APIs e feeds com permissão de uso, respeitando limites e contratos.
* Agendamento periódico, inicialmente a cada 6 horas, ajustável por fonte.
* Normalização e armazenamento de metadados, origem e última verificação.
* Deduplicação por identificador e, futuramente, por equivalência entre plataformas.
* Reconhecimento de anúncios removidos ou encerrados, com política de expiração verificável.
* Classificação da categoria por regra explícita ou revisão, sem inventar requisitos ausentes.
* Nenhuma dependência de importação manual para a operação da primeira versão.

CIEE, IEL, Nube, Gupy, Vagas.com e 99jobs são **fontes candidatas**, não conectores funcionais confirmados. A conexão deverá ser validada tecnicamente e quanto à autorização de uso.

## Interface

Página de pesquisa, lista de resultados, detalhes da vaga e botão para candidatura na fonte original. Cadastro não obrigatório para a consulta pública. Painel administrativo separado para diagnósticos de fontes, manutenção, indicadores e revisão de resultados, em etapa específica.

## Arquitetura proposta para produção

Next.js (interface), FastAPI (API), PostgreSQL e PostGIS (dados e consulta espacial), Meilisearch (busca textual), serviço de coletores em Python, agendador e Docker Compose. **Essa pilha é planejamento futuro, não representa a implementação atual em SQLite e servidor HTTP Python.**

## Requisitos mínimos de segurança

HTTPS, gestão de credenciais fora do código, validação de entradas e URLs, limitação de uso, controle de permissões, logs sem segredos, backups testados, monitoramento de fontes, adequação à LGPD e avaliação de acessibilidade.

## Critérios de aceitação propostos

* Pelo menos duas fontes externas consultadas com sucesso, com registros rastreáveis e permitidos.
* Resultados classificados nas três categorias, com testes que cubram ambiguidades.
* Filtro nacional/internacional validado em anúncios com dados geográficos reais.
* Filtro por UF, cidade e raio testado com base de municípios e coordenadas confiáveis.
* Busca acessível em computador e celular, com acesso à origem e datas verificáveis.
* Relatório de cobertura por área de formação e fonte, sem confundir quantidade de anúncios com elegibilidade real.