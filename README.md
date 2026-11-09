# Nota MGB — Avaliador de Metadados INDE

Plugin gratuito e de código aberto (GPL v2+) para **QGIS 3.28 ou superior**, desenvolvido por **Rafael Dantas de Morais (Ibexdev)**.

Dá uma nota de 0 a 100 ao metadado de cada camada segundo o **Perfil MGB 2.0** da INDE (IBGE/DSG, 2021), mostra o que falta para ficar conforme e preenche sozinho o que dá para calcular a partir da camada.

> Versão 0.1.0 (experimental).

## Funcionalidades

- **Nota de 0 a 100:** 70 pontos de conformidade (elementos obrigatórios do MGB 2.0) e 30 de qualidade (resumo, palavras-chave, linhagem, licença, SRC, contato e distribuição).
- **Selo:** Excelente, Conforme ou Não conforme. Faltou um obrigatório, o selo é Não conforme, seja qual for a nota.
- **Pendências em português**, com o quadro e a linha da norma de cada item.
- **Tipo de recurso:** recursos em geral (Quadro 84), conjunto de dados geográficos ou série (Quadro 85, padrão) e CDG do Sistema Cartográfico Nacional (Quadro 86).
- **Avaliar projeto:** todas as camadas numa tabela, da pior para a melhor.
- **Preencher automaticamente:** identificador (UUID), perfil, escopo, data do metadado, tipo de representação, extensão em graus, SRC, codificação e, em raster, o tamanho do pixel. Nunca sobrescreve um valor válido.
- **Formulário guiado:** só os campos que faltam, com as listas oficiais do MGB 2.0 em português (status, categoria temática, papel, tipo de data, idioma ISO 639-2).
- Funciona sem internet e sem chave de API.

O que o QGIS suporta é gravado no metadado nativo da camada (Propriedades da camada → Metadados). O resto fica numa propriedade do plugin salva no projeto. **Salve o projeto** depois de corrigir.

## Instalação

1. No QGIS, abra **Complementos > Gerenciar e instalar complementos**.
2. Em **Configurações**, marque **Mostrar também os complementos experimentais**.
3. Procure **Nota MGB** e clique em **Instalar**.

## Uso

1. Selecione uma camada vetorial ou raster e clique no ícone **100 MGB** da barra de ferramentas.
2. Veja a nota e as pendências na aba **Avaliar**.
3. Na aba **Corrigir**, clique em **Preencher automaticamente**, complete o formulário e clique em **Salvar e reavaliar**.
4. Salve o projeto.

## Próximas versões

- Exportar XML ISO 19115-3 (schema `iso19115-3.mgb` do catálogo da INDE) e relatório.
- Importar XML ISO 19115-3 e ISO 19139 (MGB 2009).
- Sugestões de resumo, palavras-chave e categoria com IA (opcional).

## Referência

Perfil de Metadados Geoespaciais do Brasil — Perfil MGB 2.0. IBGE/DSG, 2021.

## Licença

GNU GPL v2 ou superior. Veja [LICENSE](LICENSE).

Copyright (C) 2026 Rafael Dantas de Morais (Ibexdev) · ibexdesenvolvimento@gmail.com
