# Comic Library

Leitor de histórias em quadrinhos para desktop, feito em Python com PySide6 (Qt).
Organiza as HQs de uma pasta numa biblioteca com capas e abre cada uma num leitor página por página.

## Funcionalidades

- **Formatos:** PDF, CBR (RAR/RAR5) e CBZ (ZIP)
- **Biblioteca:** grade com as capas, etiqueta de formato, barra de progresso e busca por título
- **Continuar lendo:** cada HQ reabre na página em que você parou
- **Tela da HQ:** ao clicar numa HQ, abre uma tela com a capa grande, a descrição, série, número, ano, editora, roteiro e progresso
- **Descrições e capas online:** buscadas de graça no [Grand Comics Database](#descrições-e-capas-online), com o ComicVine como reserva opcional; também lidas do `ComicInfo.xml` do CBZ/CBR, dos metadados do PDF ou editadas à mão
- **Buscar descrições:** preenche a biblioteca inteira em segundo plano
- **Cache:** capas e metadados ficam num banco SQLite, e a biblioteca abre sem reprocessar os arquivos
- **Leitor:** página inteira ou ajustada à largura, zoom, tela cheia e navegação por teclado, mouse ou barra de páginas
- **Tema escuro**
- Lembra a última pasta aberta

## Estrutura

```
Comic_Library/
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── comics/                  # pasta padrão de HQs usada pelo Docker
└── app/
    ├── main.py              # ponto de entrada
    ├── ui/
    │   ├── main_window.py   # biblioteca (grade de capas, busca)
    │   ├── reader_window.py # leitor de páginas
    │   ├── details_page.py  # tela da HQ (capa, descrição, progresso)
    │   ├── metadata_dialog.py # edição manual dos metadados
    │   ├── settings_dialog.py # login do GCD e chave do ComicVine
    │   └── theme.py         # tema escuro
    ├── library/
    │   ├── scanner.py       # encontra as HQs numa pasta
    │   ├── metadata.py      # ComicInfo.xml, metadados do PDF e nome do arquivo
    │   ├── images.py        # miniaturas e comparação de capas
    │   └── online/          # busca de descrição e capa
    │       ├── gcd.py       # Grand Comics Database (grátis, sem chave)
    │       └── comicvine.py # ComicVine (opcional, com chave)
    ├── reader/
    │   ├── document.py      # escolhe o leitor pelo formato
    │   ├── pdf_reader.py    # PDF (PyMuPDF)
    │   └── archive_reader.py# CBR/CBZ (libarchive)
    └── database/
        └── database.py      # SQLite: capas, metadados e progresso
```

## Rodando localmente

Requisitos: Python 3.12+ e a biblioteca de sistema **libarchive** (para CBR/CBZ).

| Sistema | libarchive |
|---|---|
| Arch Linux | já vem instalada (dependência do `pacman`) |
| Debian/Ubuntu | `sudo apt install libarchive13` |
| Fedora | `sudo dnf install libarchive` |

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m app.main
```

Execute sempre a partir da raiz do projeto (`python -m app.main`), para que o pacote `app` seja encontrado.

## Descrições e capas online

Na tela da HQ, **Buscar online** procura a edição no [Grand Comics Database](https://www.comics.org) (GCD) e traz sinopse, roteirista, editora, ano e a capa. O botão **Buscar descrições**, na barra de cima, faz o mesmo para todas as HQs que ainda não têm descrição, uma de cada vez.

- **A busca usa a série, o número e o ano.** Eles vêm do `ComicInfo.xml` ou do nome do arquivo: `The Flash v3 #01 (2016)` vira série "The Flash", número 1, ano 2016. Se a busca achar a HQ errada, corrija esses campos em **Editar** e busque de novo.
- **Séries com o mesmo nome** (The Flash de 1987, 2010, 2016…) são desempatadas comparando a capa do arquivo com a capa de cada candidata.
- **Capa:** a capa online fica guardada, mas o app continua usando a do arquivo. Troque em **Capa do arquivo / Capa online**, embaixo da capa.
- **As sinopses do GCD são em inglês** e nem toda edição tem uma. Edições brasileiras existem no GCD, mas muitas vêm sem sinopse.
- **Crédito:** os dados do GCD são licenciados sob CC BY-SA 4.0, e a tela mostra a fonte com o link da edição.

### Limites e configurações

Sem login, o GCD permite poucas buscas por hora (umas 20 requisições; cada HQ usa de 2 a 6). Quando o limite é atingido, o app para a busca e diz quanto tempo falta. As HQs não encontradas são marcadas para o **Buscar descrições** não repeti-las; as interrompidas pelo limite são tentadas de novo na próxima vez.

Em **Configurações** você pode informar:

- **E-mail e senha do GCD**, de uma [conta gratuita](https://www.comics.org/accounts/register/), para ter um limite maior. A senha fica salva sem criptografia nas preferências, então use uma senha exclusiva.
- **Chave do ComicVine** ([grátis](https://comicvine.gamespot.com/api/)), usada quando o GCD não acha a HQ ou não tem a sinopse. Também pode vir da variável `COMICVINE_API_KEY`.

## Onde ficam os dados

| O quê | Linux | Windows |
|---|---|---|
| Banco (capas, descrições, progresso) | `~/.local/share/ComicLibrary/library.db` | `%LOCALAPPDATA%\ComicLibrary\library.db` |
| Preferências (última pasta, login do GCD, chave do ComicVine) | `~/.config/ComicLibrary/ComicLibrary.conf` | Registro do Windows |

Apagar o `library.db` zera o progresso e as descrições. As capas são geradas de novo na próxima abertura.

## Rodando com Docker

O app é uma interface gráfica. O container desenha as janelas na sua área de trabalho usando o socket do **Wayland** (se houver) ou do **X11**. Isso funciona em hosts **Linux**.

### 1. Coloque as HQs na pasta `comics/`

Por padrão, o compose monta `./comics` (somente leitura) em `/comics` dentro do container, e o app abre essa pasta automaticamente.

Para usar outra pasta sem copiar nada, defina `COMICS_DIR`:

```bash
COMICS_DIR=~/Downloads docker compose up
```

> Links simbólicos que apontam para fora da pasta montada não funcionam dentro do container. Use arquivos de verdade ou aponte `COMICS_DIR` para a pasta original.

### 2. Construa e rode

```bash
docker compose up --build
```

Nas próximas vezes, basta `docker compose up`. Para rodar em segundo plano, use `docker compose up -d` e, para parar, `docker compose down`.

### Usuário diferente de 1000

O container roda com o mesmo UID/GID do seu usuário, para ter acesso aos sockets gráficos e às HQs. O padrão é `1000:1000`. Se `id -u` mostrar outro número, crie um arquivo `.env` na raiz do projeto:

```bash
echo "UID=$(id -u)" > .env
echo "GID=$(id -g)" >> .env
docker compose up --build
```

### Wayland ou X11

- **Wayland** (GNOME, KDE, Hyprland, Sway…): funciona direto. O compose monta o seu `XDG_RUNTIME_DIR`, onde fica o socket do Wayland.
- **Somente X11:** libere o acesso ao servidor X para o seu usuário antes de rodar:

  ```bash
  xhost +SI:localuser:$(id -un)
  ```

Para forçar uma das duas, defina `QT_QPA_PLATFORM`:

```bash
docker compose run --rm -e QT_QPA_PLATFORM=xcb comic-library      # X11
docker compose run --rm -e QT_QPA_PLATFORM=wayland comic-library  # Wayland
```

### O que o compose monta

| Host | Container | Para quê |
|---|---|---|
| `${COMICS_DIR:-./comics}` | `/comics` (somente leitura) | suas HQs |
| `$XDG_RUNTIME_DIR` | `/tmp/runtime` | socket do Wayland |
| `/tmp/.X11-unix` | `/tmp/.X11-unix` | socket do X11 |
| volume `comic-config` | `/home/app/.config` | preferências (última pasta, login do GCD, chave do ComicVine) |
| volume `comic-data` | `/home/app/.local/share` | banco com capas, descrições e progresso |

> O container tem acesso ao `XDG_RUNTIME_DIR` da sua sessão. Isso é necessário para o Wayland e é comum em apps gráficos em Docker, mas significa que ele não fica isolado da sua sessão de desktop.

## Atalhos do leitor

| Ação | Teclas / mouse |
|---|---|
| Próxima página | `→`, `Espaço`, `Page Down`, clique nos 2/3 direitos da página |
| Página anterior | `←`, `Backspace`, `Page Up`, clique no terço esquerdo |
| Primeira / última | `Home` / `End` |
| Página inteira / largura | `P` / `W` |
| Zoom | `+` / `-`, ou `Ctrl` + roda do mouse |
| Tela cheia | `F` ou `F11` |
| Sair da tela cheia / fechar | `Esc` |

No modo página inteira, a roda do mouse também vira as páginas.

## Solução de problemas

- **`qt.qpa.xcb: could not connect to display`**: no X11, rode o `xhost` indicado acima. Confira também se `echo $DISPLAY` mostra algo no host.
- **`Failed to create wl_display`**: o host não está em Wayland. O Qt tenta o X11 em seguida (veja o item anterior).
- **Nenhuma HQ aparece:** confira se os arquivos estão em `comics/` (ou em `COMICS_DIR`) e têm extensão `.pdf`, `.cbr` ou `.cbz`.
- **Erro de permissão nos sockets:** o UID do container é diferente do seu. Veja [Usuário diferente de 1000](#usuário-diferente-de-1000).

## Próximos passos

- Ordenar a biblioteca por "lidas recentemente"
- Traduzir as sinopses para português
- Leitura de páginas duplas lado a lado
- Modo de leitura da direita para a esquerda (mangá)
