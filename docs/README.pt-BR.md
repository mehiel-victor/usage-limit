# Usage Limit

**Acompanhe limites de IA, tarefas do Codex e worktrees do Git enquanto programa.**

Widget flutuante para Linux com suporte a **Codex, Antigravity e Claude Code**, feito com Python, GTK 3 e Cairo.

[English](../README.md) · [Uso e configuração (inglês)](usage.md) · [Como contribuir](../CONTRIBUTING.md) · [Versões](https://github.com/mehiel-victor/usage-limit/releases)

<picture>
  <source media="(prefers-color-scheme: light)" srcset="../assets/preview-light.png">
  <img alt="Usage Limit com limites de uso, status de tarefas do Codex, worktrees do Git e modo compacto" src="../assets/preview.png">
</picture>

*Prévia renderizada pelo código Cairo do aplicativo com dados fictícios. A interface atual está em português.*

## O que ele faz

- **Limites visíveis:** percentuais restantes e horários de renovação; alterne entre provedores e janelas disponíveis.
- **Tarefas do Codex:** veja tarefas recentes, abra a fila de tarefas ativas e retorne à conversa no Codex Desktop.
- **Worktrees do Git:** consulte branches à frente de uma referência local de main e alterações em arquivos rastreados, sem modificar repositórios.
- **Modo compacto:** recolha o widget em três cápsulas de provedores na borda direita e clique para expandir.
- **Controles de desktop:** fixação, passagem de cliques, redimensionamento, troca de monitor, tema claro/escuro automático e posição salva.

O widget não adiciona telemetria nem envia notificações de desktop ou tela bloqueada. Ele lê a saída das CLIs e dados locais de tarefas; as CLIs podem acessar os serviços dos respectivos provedores. Veja [acesso a dados e limitações](usage.md#data-access-and-limitations).

## Instalação rápida

Requer **Linux, Python 3.10+, GTK 3, PyGObject e Cairo**, além de pelo menos um provedor configurado. O inicializador usa **X11** por padrão; sessões Wayland precisam de **XWayland**. Não há suporte a Wayland nativo, macOS ou Windows.

No Debian/Ubuntu, instale as dependências do sistema:

```bash
sudo apt update
sudo apt install git python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 librsvg2-common
```

Clone e execute:

```bash
git clone https://github.com/mehiel-victor/usage-limit.git
cd usage-limit
./launch-usage-limit
```

| Provedor | Configuração |
| --- | --- |
| Codex | Instale o Codex e faça login. O widget consulta os limites pelo app server local. |
| Antigravity | Instale e autentique a CLI do Antigravity com saída estruturada de `/usage`. |
| Claude Code | Configure a [ponte opcional de status line](usage.md#claude-code). |

Um provedor indisponível não impede a leitura dos demais. Para abrir tarefas, é necessário o Codex Desktop com o protocolo `codex://` registrado. A visão de worktrees requer Git.

## Adicionar ao menu de aplicativos

```bash
./install.sh
```

O script registra um atalho e um ícone para o usuário atual. O atalho aponta para esta pasta: mantenha o clone no mesmo lugar. O script não instala dependências nem inicia o widget automaticamente.

Para atualizar, execute `git pull --ff-only` e reinicie o widget. Para remover o atalho e o ícone gerenciados:

```bash
./uninstall.sh
```

Os scripts preservam arquivos gerenciados que foram modificados. A remoção não apaga o clone, a configuração dos provedores nem as preferências do widget.

## Primeira contribuição

Relatos de problemas, testes de instalação, documentação, traduções e código são bem-vindos. Comece pelo [guia de contribuição](../CONTRIBUTING.md) e pelas [issues para iniciantes](https://github.com/mehiel-victor/usage-limit/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22).

Algumas áreas úteis: instruções para outras distribuições, testes dos parsers com dados fictícios e compatibilidade entre desktops. Ao relatar um problema, informe a distribuição Linux e o tipo de sessão.

Verificações básicas locais:

```bash
python3 -m compileall -q ./*.py
sh -n install.sh
sh -n uninstall.sh
bash -n launch-usage-limit
```

Esses comandos verificam sintaxe; não substituem o teste no desktop nem as integrações com provedores. O fluxo completo está em [CONTRIBUTING.md](../CONTRIBUTING.md).

Se a ferramenta for útil, deixe uma estrela para ajudar outras pessoas a encontrá-la. Compartilhar seu ambiente e contribuir com uma correção também ajuda o projeto.

## Licença e créditos

O código usa a [licença MIT](../LICENSE). As marcas dos provedores pertencem aos respectivos titulares; veja os [créditos dos assets](../assets/README.md). Este é um projeto independente da comunidade, sem vínculo oficial com OpenAI, Google ou Anthropic.

O tratamento visual se inspira em [Liquid Glass for GNOME Shell](https://github.com/ryohsuke1231/liquid-glass), sem exigir a extensão ou seus shaders. Consulte o [Código de Conduta](../CODE_OF_CONDUCT.md) e a [política de segurança](../SECURITY.md).
