# Especificação funcional e técnica | Portal de Estágios

Versão 1.0 | 30 de outubro de 2026 | Documento de proposta

## 1. Objetivo e abrangência

Localizar e apresentar oportunidades de estágios no Brasil e no exterior, para estudantes de todos os cursos técnicos e superiores. O portal é instrumento de descoberta e apoio à decisão, não de autorização ou formalização de estágio. A candidatura ocorre exclusivamente no site oficial da oportunidade.

## 2. Princípios

1. Nenhuma oportunidade será exibida como validada academicamente sem aprovação institucional explícita.
2. Toda vaga exibida possuirá origem verificável, link original e data da última observação.
3. Dados ausentes não serão inferidos como fatos, inclusive país, remuneração, elegibilidade internacional e modalidade.
4. Classificação automatizada é hipótese sujeita a revisão humana.
5. O sistema não fará submissão automática de candidaturas.
6. Dados pessoais dos estudantes serão minimizados; na primeira versão, pesquisa pública sem cadastro de aluno.
7. Fontes serão coletadas somente por meios permitidos e condições de uso verificadas.

## 3. Perfis e permissões

* Visitante: consultar, filtrar e abrir a oportunidade original.
* Curador: revisar, corrigir metadados, bloquear anúncios e identificar possíveis fraudes.
* Administrador: gerenciar cursos, fontes, responsáveis, permissões e indicadores técnicos.
* Empresa parceira: cadastro de vagas mediante fluxo supervisionado na segunda versão.
* Aluno autenticado: salvar buscas e acompanhar candidaturas na segunda versão.

Todos os acessos administrativos deverão usar autenticação institucional ou provedor confiável, controle de permissões e auditoria. A autenticação não faz parte do código da prova de conceito.

## 4. Requisitos funcionais da primeira versão

RF01: pesquisar título, área de formação e descrição em português e, progressivamente, outros idiomas.
RF02: filtrar por curso ou área, país, localidade e modalidade, quando conhecidos.
RF03: distinguir tipo da oportunidade: estágio, programa de pesquisa, trainee, emprego ou indeterminado.
RF04: apresentar organização, fonte, URL, localização, prazo, carga horária e remuneração, somente quando publicados.
RF05: ingerir dados por adaptadores de fontes autorizadas e por cadastro manual supervisionado.
RF06: registrar identificador da fonte, momento da coleta e histórico de alterações.
RF07: detectar duplicidades exatas por identificador e versões repetidas de uma mesma vaga entre fontes.
RF08: encaminhar classificações duvidosas para fila de revisão.
RF09: permitir ocultar anúncios encerrados, expirados ou suspeitos.
RF10: oferecer canal para sinalizar anúncios problemáticos.
RF11: distinguir claramente oportunidades descobertas de vagas institucionalmente analisadas.
RF12: manter catálogo de cursos, níveis, campi e palavras equivalentes em outros idiomas.
RF13: disponibilizar API pública de consulta com limites de uso e sem dados pessoais.
RF14: apresentar interface responsiva e acessível por teclado e leitores de tela.

**RF01, RF03, RF05 e RF07 estão implementados apenas parcialmente no protótipo.** RF06 guarda última consulta sem trilha histórica. O restante requer desenvolvimento.

## 5. Requisitos não funcionais

* RNF01: criptografia TLS no ambiente publicado, segredos fora do repositório, privilégios mínimos e proteção contra abusos.
* RNF02: observabilidade da coleta, falhas, quantidade de vagas por fonte, latência e erros de classificação.
* RNF03: backups, testes de restauração, migrações de banco e plano de continuidade.
* RNF04: conformidade com LGPD, termos das fontes e política institucional de retenção.
* RNF05: acessibilidade conforme WCAG 2.2 AA, verificada na interface real.
* RNF06: consultas com resposta em até 2 segundos no percentil 95 como meta inicial, dependente de teste de carga.
* RNF07: evitar dependência obrigatória de serviços pagos de IA.

## 6. Fonte de dados, conformidade e abrangência

| Fonte | Mecanismo proposto | Estado da prova de conceito |
| --- | --- | --- |
| Greenhouse | API de listagem de vagas publicadas de empresas cadastradas | Conector codificado, sem teste de rede |
| Lever | API de anúncios publicados com paginação | Conector codificado, sem teste de rede |
| Ashby | API pública de job board | Conector codificado, sem teste de rede |
| CIEE, IEL e Nube | Negociação de parceria ou cadastro assistido | Não integrado |
| Empresas conveniadas | Cadastro supervisionado e possível API | Não integrado |
| Editais e instituições internacionais | Cadastro assistido ou importação autorizada | Não integrado |

As APIs dos três provedores são **organizadas por empresa**, não mecanismos universais de busca por todos os estágios. É necessário formar um catálogo de organizações, verificar permissões e medir cobertura por curso. Fontes internacionais normalmente têm melhores dados de recrutamento empresarial, mas podem deixar de fora licenciaturas, áreas rurais, saúde e estágios brasileiros.

## 7. Taxonomia e correspondência com cursos

Entidades principais: `course`, `campus`, `course_alias`, `opportunity`, `opportunity_source`, `organization`, `eligibility_evidence`, `source_run`, `review_decision`, `reported_issue`, `audit_event`. A identidade de cada anúncio deve reter provedor e identificador externo; duplicidades entre fontes são armazenadas como relação, preservando as origens.

Cada correspondência curso e vaga deverá registrar: critério textual observado, trecho do requisito original, condição obrigatória ou desejável, pontuação heurística e revisão humana. Não classificar como apto um aluno simplesmente porque a área é semelhante. Requisitos de idioma, residência, visto, matrícula local e período do curso deverão aparecer como declarados, desconhecidos ou incompatíveis, nunca pressupostos.

Exemplos de áreas a testar: Tecnologia, Administração, Agropecuária, Saúde, Licenciaturas, Engenharia, Comunicação e Direito. A lista é extensível, não define previamente todos os cursos atendidos.

## 8. Arquitetura proposta para produção

Frontend: Next.js ou SvelteKit, após avaliação de experiência da equipe.
API: FastAPI com contratos OpenAPI e autenticação para funções administrativas.
Processamento: Python em tarefas controladas, com adaptadores independentes por provedor.
Persistência: PostgreSQL para vagas, cursos, fontes, revisões e eventos.
Busca: PostgreSQL com índices textuais inicialmente; Meilisearch quando avaliação real justificar.
Implantação: Docker Compose em piloto, proxy HTTPS, backups e monitoramento.

A prova de conceito usa somente biblioteca padrão do Python, SQLite e servidor HTTP local para testar o fluxo mínimo, evitando custo operacional precoce.

## 9. Fluxo de oportunidade

`fonte cadastrada -> coleta permitida -> validação de esquema -> normalização -> deduplicação -> classificação -> revisão -> publicação -> revalidação -> arquivamento`.

Uma falha na fonte não deve apagar vagas imediatamente. O sistema de produção deverá usar janelas de tolerância e verificação repetida antes de sinalizar encerramento.

## 10. MVP versus versões posteriores

### MVP de produto

Pesquisa, filtros, catálogo de cursos, fontes verificadas, coleta e cadastro assistido, deduplicação, curadoria, sinalização de erros, atualização de disponibilidade, API de consulta, acessibilidade e painel técnico.

### Versão 2

Perfil opcional do aluno, favoritos, alertas por email, empresas parceiras, acompanhamento voluntário de candidaturas, pesquisa multilíngue ampliada e indicadores acadêmicos agregados.

### Versão 3

Integração autorizada com sistemas acadêmicos, regras por PPC, documentação de estágio, tramitação administrativa e análises de tendências.

## 11. Prova de conceito entregue

Arquivos `core.py`, `app.py`, `sources.json` e `tests/`.

Implementado: clientes de três APIs para empresas previamente listadas, parsing do retorno, classificação por títulos, associação inicial a áreas, deduplicação determinística por chave, SQLite, consulta HTTP e página web simples. O modo demonstração é **fictício e identificado**.

Não implementado: autenticação, curadoria administrativa, agendamento, histórico de alterações, deduplicação entre provedores, classificação avançada, verificação de encerramento, classificação curricular, segurança para produção ou validação jurídica das fontes.

## 12. Plano de prova real e critérios de decisão

1. Selecionar e documentar 5 organizações por provedor, contemplando empregadores brasileiros e internacionais, com job boards oficiais e permissões verificadas.
2. Executar coletores em ambiente isolado, medir taxa de sucesso e registrar códigos de resposta, sem exceder limites.
3. Construir amostra de ao menos 200 anúncios de setores variados, com revisão humana para determinar quais são efetivamente estágios.
4. Medir precisão e cobertura da classificação, duplicidades e distribuição por curso, região e país. Não estabelecer metas de acurácia sem amostra rotulada.
5. Comparar custo e manutenção de integrar Freehire com custo e manutenção dos adaptadores próprios, incluindo análise da licença.
6. Decidir arquitetura definitiva e só então migrar para PostgreSQL e iniciar interface final.

## 13. Riscos e tratamento

* Cobertura insuficiente para cursos não tecnológicos: fontes brasileiras e parcerias institucionais, com acompanhamento por área.
* Vagas internacionais inacessíveis a brasileiros: exigir evidência explícita de elegibilidade ou indicar estado desconhecido.
* Bloqueio e termos de uso: catálogo de permissões por fonte, sem contornar controles.
* Falsos positivos: triagem e avaliação amostral, sem apresentar classificação como certeza.
* Anúncios fraudulentos: denúncias, revisão e preservação da URL original, com política de remoção.
* Dados pessoais: não coletar currículos nem dados de estudantes no MVP.
* Trabalho de manutenção: métricas por conector, versionamento e testes com fixtures.

## 14. Critérios de aceite da prova de conceito

* Instalação em Python sem dependências externas.
* Oito testes unitários passando localmente.
* Quatro registros fictícios carregáveis, todos claramente identificados.
* Busca HTTP e API de leitura no computador local.
* Fontes reais inativas até configuração explícita.

**Critérios ainda pendentes para o MVP público:** execução real autorizada de pelo menos duas fontes, revisão humana, medidas de segurança, acessibilidade testada, métricas de relevância por curso, painel de curadoria e infraestrutura de produção.

## 15. Referências oficiais

* https://docs.greenhouse.io/job-board
* https://github.com/lever/postings-api
* https://developers.ashbyhq.com/docs/public-job-posting-api
* https://github.com/strelov1/freehire