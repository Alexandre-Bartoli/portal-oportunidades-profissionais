# Pesquisa geográfica experimental

O catálogo utiliza as sedes municipais do Censo Demográfico 2022, produto Localidades do Brasil, do IBGE. Há 5.570 municípios distintos na base extraída. Arquivos em `data_geo` contêm somente código IBGE, nome, UF e coordenadas da sede, arredondadas a quatro casas decimais. A origem e a soma SHA256 do arquivo recebido estão em `data_geo/fonte.json`.

Na interface, selecione um estado e pesquise para carregar sua lista de municípios. Selecione o município e, se desejar, informe um raio entre 0 e 2.000 km. Sem raio, o filtro retorna somente o município selecionado. Com raio, são consideradas também sedes de outros estados dentro da distância calculada.

A distância é aproximada, em linha reta, entre as sedes dos municípios. Não representa distância por estrada, o limite do município ou o endereço da vaga. Estabelecimentos distantes da sede podem aparecer dentro ou fora do raio por essa aproximação.

Uma vaga recebe um código geográfico somente em nova coleta ou atualização quando o país informado pelo conector é BR e a localização corresponde de modo inequívoco ao formato `Município, UF`, com eventual sufixo Brasil. Vagas remotas, nomes múltiplos, ausentes ou ambíguos ficam sem código e não aparecem nos filtros geográficos. Os dados originais são preservados; nenhuma localização antiga é preenchida automaticamente na migração. As fontes variam na forma como informam localização e a cobertura será parcial. Dados fornecidos pela fonte continuam sujeitos a erro e revisão.

Na API, combine `uf=MG`, `municipality=3105608` e `radius_km=100`. O código é o identificador oficial do município e `distance_km` é a distância aproximada entre sedes. Município exige a UF correspondente; raio exige município. Parâmetros inválidos retornam HTTP 400.

A migração SQLite é aditiva e registrada como versão 2. Faça backup antes de atualizar. Restaurar versões anteriores da aplicação pode exigir a restauração de uma cópia anterior do banco; teste o procedimento em homologação. A migração não reescreve registros existentes.

Fonte original: [IBGE, Localidades do Brasil](https://www.ibge.gov.br/estatisticas/sociais/saude/27385-localidades.html). A extração utilizou registros da categoria Cidade com código de localidade igual ao código do município, eliminando cópias idênticas de capitais. A base oficial é de referência de 2022 e não atualiza alterações municipais posteriores automaticamente.

Para reproduzir o catálogo com o mesmo arquivo oficial, execute `python ops/extrair_municipios_ibge.py Localidades_Brasil_gpkg.zip diretorio_saida`. O script confere a soma SHA256, a quantidade de municípios e eventuais duplicatas conflitantes. Uma edição diferente do IBGE precisa de revisão e atualização explícita da soma esperada.
