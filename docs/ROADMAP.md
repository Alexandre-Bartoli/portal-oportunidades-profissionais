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