# Auditoria inicial, 7 de novembro de 2026

Referência: commit 82c72f4221a263aa0eb8318b1dba0ed51355a781 da branch main. Esta é uma avaliação inicial, não uma auditoria integral nem aprovação para produção.

## Evidências

* Os 120 testes existentes passaram localmente em Python, com rede simulada. A execução não comprova disponibilidade de fontes reais.
* O fluxo Testes Python do GitHub para o commit de referência concluiu com sucesso. O repositório registra uma homologação anterior em runner temporário, sem serviço persistente.
* O servidor usa a biblioteca padrão do Python, SQLite e escuta somente em loopback. A interface e os comandos estão em app.py; os dados são tratados por core.py, homologacao.py e stage_storage.py.
* A migração SQLite é aditiva e usa PRAGMA user_version; os testes existentes abrangem dados legados, cópia e restauração simuladas em diretórios temporários. Integridade referencial deve ser verificada e habilitada explicitamente por conexão antes de depender dela em produção.
* O armazenamento de homologação usa backup local e modelos de agendamento. Esses arquivos não comprovam backup externo, hospedagem persistente nem monitoramento ativo.

## Riscos e pendências

* Não há autenticação administrativa, limitação de requisições ou configuração de implantação pública e HTTPS no código analisado. O servidor de desenvolvimento não deve ser exposto à internet.
* A revisão de condições de uso e republicação das fontes está pendente. Acesso técnico a uma API não estabelece autorização para publicar anúncios.
* Pesquisa por estado, município e raio, uso de dados geográficos oficiais, detalhes completos, acessibilidade e painel administrativo permanecem incompletos ou sem validação suficiente.
* O SQLite pode ser adequado à homologação inicial; nenhuma medição aqui justifica migrar para PostgreSQL ou PostGIS. Concorrência e volume exigem testes com a carga esperada antes da decisão.
* A classificação, a deduplicação, a identificação de país e os sinais de qualidade são heurísticos. Não se deve tratar esses resultados como fatos confirmados.
* Não foram testadas nesta avaliação fontes externas, links individuais, testes de carga, segurança em produção, recuperação fora da máquina ou atendimento à legislação. Não há comprovação de um endereço público operacional.

## Correção proposta nesta branch

Respostas Greenhouse, Lever e Ashby com registros que não sejam objetos ou sem título ou endereço HTTPS são rejeitadas em vez de apresentadas como inventário completo. Isso evita que tais respostas acionem a lógica de ausência de anúncios. A validação cobre esses casos específicos; outros campos, conectores e mudanças na estrutura dos provedores continuam exigindo avaliação.

## Próximos passos

Validar cada provedor e seus termos, testar a coleta real em ambiente autorizado, revisar os demais conectores e proteger a publicação. Implantação exige uma hospedagem persistente, separação dos ambientes, domínio ou endereço, HTTPS, agendamento, backups externos, recuperação e monitoramento comprovados. Custos dependem do serviço escolhido e não foram cotados nesta avaliação.
