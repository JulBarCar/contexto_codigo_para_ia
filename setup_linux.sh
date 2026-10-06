#!/usr/bin/env bash

set -e

echo "================================"
echo " Instalador de code-context"
echo "================================"
echo ""

# Verificar python3
if ! command -v python3 &> /dev/null
then
    echo "Python3 no está instalado."
    echo "Instálalo con:"
    echo "sudo apt install python3"
    exit 1
fi

# Verificar que el archivo exista
if [ ! -f "code_context.py" ]; then
    echo "No se encontró code_context.py en esta carpeta."
    echo "Ejecuta el instalador desde la raíz del proyecto."
    exit 1
fi

INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="contexto"

mkdir -p "$INSTALL_DIR"

# Copiar script + modulo (code_context.py importa modules.*)
cp code_context.py "$INSTALL_DIR/code_context.py"
rm -rf "$INSTALL_DIR/modules"
cp -r modules "$INSTALL_DIR/modules"
find "$INSTALL_DIR/modules" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null

# Instalar skill de opencode para agentes IA
SKILL_DIR="$HOME/.config/opencode/skills/contexto"
if [ -f "skills/contexto/SKILL.md" ]; then
    mkdir -p "$SKILL_DIR"
    cp skills/contexto/SKILL.md "$SKILL_DIR/SKILL.md"
    echo "Skill de opencode instalada en $SKILL_DIR"
else
    echo "No se encontró skills/contexto/SKILL.md, se omite la skill."
fi

echo '#!/usr/bin/env bash' > "$INSTALL_DIR/$SCRIPT_NAME"
echo 'python3 "$HOME/.local/bin/code_context.py" "$@"' >> "$INSTALL_DIR/$SCRIPT_NAME"

chmod +x "$INSTALL_DIR/$SCRIPT_NAME"

# Verificar PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    if [ -f "$HOME/.bashrc" ] && ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    fi
    echo ""
    echo "Se agregó ~/.local/bin al PATH en .bashrc"
    echo "Reinicia la terminal."
fi

echo ""
echo "================================"
echo "Instalación completada."
echo ""
echo "Usa:"
echo "contexto ."
echo "================================"
