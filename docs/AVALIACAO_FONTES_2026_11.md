# Fontes e adaptações experimentais

Esta etapa adiciona adaptadores experimentais em Python. A Gupy está ativada em caráter experimental por opção do responsável; Sólides, Remotive e Workable permanecem desativadas. Testes com respostas simuladas não comprovam disponibilidade, permissão de coleta ou direito de republicação.

A busca da Gupy utiliza a mesma rota pública de pesquisa estudada no Job Pindorama, sem token. Quando o endereço retornado identifica com segurança uma página de empresa e o identificador numérico da vaga, o adaptador gera o endereço direto da vaga; caso contrário preserva o endereço válido retornado. O campo experimental_access habilita a consulta sem registrar aprovação documental. Para interromper, desative as entradas Gupy em sources.json.

## Resultado da investigação

| Fonte | Preparação e limites | Situação |
| --- | --- | --- |
| Gupy | Paginação limitada, detecção de repetição e respostas inválidas. Consulta filtrada permanece parcial. | Ativada experimentalmente; revisão de acesso, republicação e teste integrado pendentes. |
| Sólides | Uma página por pesquisa; categorias conservadoras. Local e país não são inferidos como confirmados. | Desativada; condições de acesso e publicação e teste real pendentes. |
| VAGAS.com | Os termos consultados tratam de direitos sobre conteúdos e de reprodução com autorização. | Nenhuma coleta automática foi criada ou ativada; verificar autorização aplicável. |
| Workable | Adaptador de widget por organização, sem busca global; não implica acesso à API autenticada de clientes. | Não há organização configurada; revisão e teste real pendentes. |
| InHire | Adaptador por identificador de empresa e consulta ao detalhe de cada anúncio, inspirado no Radar de Vagas. | Nenhuma empresa configurada; revisão e teste real pendentes. |
| Remotive | Feed remoto; o link de candidatura aponta à Remotive e o nome da fonte aparece no portal. A localização retornada representa restrição geográfica de candidatura, não o endereço da vaga. | Desativada; condições e validação real pendentes. |

Fontes consultadas em 8 de novembro de 2026: [VAGAS.com, termos de uso](https://www.vagas.com.br/candidatos/termos-de-uso); [Workable, API para página de carreiras](https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page); [Remotive, condições da API](https://remotive.com/remote-jobs/api); [documentação da API Remotive](https://github.com/remotive-com/remote-jobs-api); [Gupy, página de carreiras externa](https://developers.gupy.io/docs/fluxo-de-pagina-de-carreiras). A documentação de página de carreiras da Gupy não é prova de autorização para o endpoint do portal usado no experimento. Não foi confirmada permissão de republicação para Sólides ou Workable.

Em 9 de novembro de 2026, uma consulta direta no navegador à busca pública da Gupy, limitada a um resultado de estágio, retornou um anúncio com identificação, empresa, localização e link. A execução do adaptador neste ambiente teve tempo esgotado; a consulta pelo navegador não confirma coleta integrada nem cobertura completa.

Na Gupy, até os três primeiros resultados por categoria recebem tentativa de detalhe por coleta. A página deve ser uma URL HTTPS de vaga de uma empresa Gupy; redirecionamentos são recusados. Descrição, atividades e requisitos são reunidos e o país é preenchido apenas se a página o informar. Uma falha de detalhe preserva a listagem. As contagens de detalhes tentados e obtidos constam no relatório e no painel. As demais vagas permanecem com dados da listagem e podem não aparecer no filtro por país. O teto prioriza sempre os primeiros resultados, não garante cobertura de todos os anúncios.

A Remotive informa que a API pública tem atraso de 24 horas, solicita atribuição e link à Remotive, impõe restrições de redistribuição e recomenda no máximo quatro consultas por dia. O código reserva no SQLite um intervalo mínimo de seis horas entre tentativas e não repete automaticamente uma mesma requisição. O limite é compartilhado apenas por processos que usam o mesmo diretório de código e `data`; não é uma limitação distribuída entre servidores. O arquivo de limites precisa ser persistente para que reinícios mantenham a restrição. A verificação das condições aplicáveis ao uso específico do portal continua pendente.

Sólides, Workable, InHire e Remotive exigem revisão técnica documental antes de serem consultadas pelas rotinas automáticas, de homologação ou de auditoria. A Gupy pode ser consultada com a opção experimental_access, mantendo a revisão marcada como pendente. Isso não confirma permissão para republicação. As fontes antigas já habilitadas continuam exigindo revisão antes de qualquer publicação.

## Duplicatas e sinais

O painel administrativo lista possíveis duplicatas quando título, país, localização e uma descrição suficientemente longa são idênticos após normalização. O agrupamento é apenas um sinal: não exclui nem mescla anúncios. A inspeção padrão cobre até 1.000 registros ativos mais recentes e indica quando está incompleta. O painel de detalhes mostra sinais para revisão, sem declarar fraude ou inelegibilidade.

## Migração e proveniência

A migração aditiva do banco chega à versão 4. A versão 3 acrescentou empresa e data de publicação; a versão 4 registra se o detalhe da Gupy foi obtido, para preservar informações já enriquecidas quando uma consulta posterior retornar apenas a listagem. Faça backup antes de atualizar e teste a restauração em homologação.

Os padrões das rotas, estrutura de módulos e validações foram estudados em [Job Pindorama](https://github.com/rosanapegasgodoy/job-pindorama), [AI Job Search](https://github.com/ai-job-search-dev/ai-job-search) e [Career Ops](https://github.com/career-ops-hq/career-ops). Os adaptadores deste portal foram implementados em Python para este código, sem copiar integralmente os componentes TypeScript ou JavaScript. As licenças MIT consultadas estão em `docs/licencas_referencias/`. A licença do código de referência não concede automaticamente direitos sobre os anúncios de terceiros.

O detalhamento da Gupy e o adaptador InHire foram adaptados em Python a partir do [Radar de Vagas](https://github.com/dspinillo/radar-de-vagas) de Dhiego Spinillo, revisão `3eeb01f07fc4af7f3703d23e809c37e584b69df0`. O aviso MIT original acompanha o projeto em `docs/licencas_referencias/RADAR_DE_VAGAS_MIT.txt`. A licença do código não é autorização de uso dos anúncios.

Não há cadastro de candidato, análise individual de currículo, criação de currículo ou acompanhamento de candidaturas nesta etapa. Esses recursos exigem um módulo separado e controles apropriados de acesso e privacidade.
