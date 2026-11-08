# Roteiro de desenvolvimento

## Estado atual (prova de conceito)

- [x] Servidor HTTP local e API JSON
- [x] Conectores Greenhouse, Lever e Ashby implementados
- [x] Agendamento enquanto a aplicação está aberta
- [x] Classificação heurística de estágios
- [x] Banco SQLite local
- [x] Testes unitários sem rede
- [ ] Coleta de vagas reais comprovada nas fontes configuradas

## Versão 0.4: confiabilidade local

- [x] Tratamento de erros transitórios com tentativas limitadas
- [x] Verificação do formato das respostas de provedores
- [x] Registro por fonte de consultas bem sucedidas e falhas
- [x] Inativação após duas ausências consecutivas em consultas válidas
- [x] Preservação de anúncios quando uma consulta falha
- [x] Testes automáticos do ciclo de vida e de repetição das requisições
- [ ] Validação externa de coletas reais, pendente de acesso DNS e verificação de fontes

## Próximo ciclo: coleta validada

- [ ] Verificar permissões e documentações de cada fonte
- [ ] Testar respostas reais das APIs com organizações ativas
- [ ] Tratar erros de rede, limites de acesso e paginação por provedor
- [ ] Registrar idade do anúncio e política de remoção
- [ ] Expandir fontes para múltiplas áreas, não somente tecnologia

## MVP funcional aprovado

- [ ] Classificação de estágio, emprego e temporário
- [ ] Seleção de abrangência Brasil, exterior e ambos
- [ ] Catálogo de municípios/UF e consulta de raio geográfico
- [ ] Filtros de área de formação, modalidade e local
- [ ] Interface web e administração básica de fontes
- [ ] Sinalização de anúncios expirados e suspeitos
- [ ] Acessibilidade e verificações de segurança

## Pós MVP

- [ ] Usuários autenticados e alertas personalizados
- [ ] Histórico de candidaturas
- [ ] Convênios e gestão acadêmica de estágios
- [ ] Integração com sistemas acadêmicos

**Não considerar itens pendentes como implementados.**

## Evolução experimental 0.5

- [x] Estudar Job Pindorama e AI Job Search original
- [x] Criar adaptador Python experimental de consulta Gupy
- [x] Preservar fonte desabilitada por padrão até revisão de acesso
- [x] Distinguir estágio, emprego e temporárias por anúncio
- [x] Acrescentar alertas sobre inconsistência da descrição
- [x] Permitir filtro de categoria na interface e API
- [x] Testar os componentes com respostas simuladas
- [ ] Validar a coleta real Gupy e autorização de uso
- [ ] Medir cobertura de empregos e temporárias em fontes habilitadas
- [ ] Testar deduplicação entre portais e qualidade dos anúncios

## Versão experimental 0.6: provedores e identidade

- [x] Registro de provedores SmartRecruiters e Breezy, desativados por padrão
- [x] Funções de reconhecimento de endereços de ATS
- [x] Descoberta passiva de sugestões de fontes após a coleta
- [x] Deduplicação por URL canônica com origens independentes no SQLite
- [x] Migração aditiva de banco e auditoria não destrutiva de duplicatas antigas
- [x] Não encerrar vagas com base em respostas paginadas incompletas
- [ ] Testar conectores com rede e validar termos de uso de cada fonte
- [ ] Construir descoberta ativa controlada em páginas de carreiras autorizadas
- [ ] Revisão assistida de duplicatas antigas com backup e histórico
- [ ] Deduplicação entre URLs diferentes da mesma oportunidade com validação humana
- [ ] Teste de carga, segurança e implantação multiusuário

## Versão 0.7: validação demonstrável de fontes

- [x] Auditar fontes habilitadas sem gravar nem desativar registros no banco
- [x] Separar anúncios originais recebidos de vagas classificadas pelo portal
- [x] Distinguir `empty`, `no_match`, `partial`, `invalid_data` e `error`
- [x] Gerar relatório estruturado com resultados por fonte e critério mínimo
- [x] Criar execução manual no GitHub Actions, sem credenciais ou dados pessoais
- [x] Ampliar cobertura de testes com respostas simuladas
- [ ] Confirmar pelo menos duas fontes independentes com anúncios reais
- [ ] Verificar links e qualidade dos anúncios manualmente
- [ ] Revisar as condições de consulta e utilização de cada fonte
- [ ] Repetir testes em datas diferentes para demonstrar estabilidade

A execução local em 07/11/2026 apresentou quatro erros de rede e **não
comprova coleta real**. Veja [a documentação](VALIDACAO_07.md).

## Versão experimental 0.8: homologação isolada

- [x] Criar banco SQLite independente da base principal
- [x] Validar inventário antes de salvar cada fonte
- [x] Registrar estados por fonte e estatísticas de anúncios armazenados
- [x] Persistir vagas compatíveis, mantendo deduplicação e origem
- [x] Preservar vagas após erros de consulta ou inventários parciais
- [x] Impedir inclusão de anúncios de demonstração
- [x] Servir resultados pela interface/API apenas em endereço local separado
- [x] Criar testes de fluxo completo e workflow de auditoria no GitHub Actions
- [x] Confirmar persistência de 7 vagas reais no runner externo em uma execução
- [ ] Conferir amostra de links individuais e condições de utilização
- [ ] Implantar homologação privada persistente com backups e proteção de acesso
- [ ] Publicar portal para usuários finais após revisão técnica e jurídica

Ver [procedimento de homologação](HOMOLOGACAO_08.md).

Evidência externa da versão 0.8: [relatório de homologação](EVIDENCIA_HOMOLOGACAO_08.md).