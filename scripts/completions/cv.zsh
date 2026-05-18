#compdef cv uv python python3

# Zsh completion for CV CLI.
# Supports:
#   cv <command> ...
#   uv run main.py <command> ...
#   python main.py <command> ...

_cv_commands=(
  'bot:Start Telegram bot'
  'apply:Generate application from a job URL'
  'preview:Generate preview CV bundle'
  'init-profile:Parse CV source into profile JSON'
  'init_profile:Alias for init-profile'
  'test:Run environment sanity checks'
  'help:Show help'
)

_cv_templates=(
  'altacv:AltaCV template'
  'lato:Lato template'
)

_cv_roles=(
  'ai:AI/Data roles'
  'it:IT/Infrastructure roles'
  'phd:PhD/Research roles'
)

_cv_langs=(
  'auto:Auto-detect from posting'
  'fr:French'
  'en:English'
  'fa:Persian'
  'es:Spanish'
  'de:German'
  'it:Italian'
)

_cv_colors=(
  'blue'
  'green'
  'orange'
  'red'
  'purple'
  'gray'
)

_cv_apply_opts=(
  '--template:CV template'
  '--lang:Output language'
  '--color:Color theme'
  '--no-fallback:Disable offline fallback'
)

_cv_preview_opts=(
  '--template:CV template'
  '--role:Profile role'
  '--lang:Output language'
  '--color:Color theme'
  '--no-localize-preview:Disable preview localization'
)

_cv_init_profile_opts=(
  '--cv:Input CV file (.tex/.pdf/.jpg/.png/.webp)'
)

_cv_complete_core() {
  local subcmd prev cur
  cur="${words[CURRENT]}"
  prev="${words[CURRENT-1]}"
  subcmd="${words[2]}"

  # Complete subcommand
  if (( CURRENT == 2 )); then
    _describe -t commands 'cv command' _cv_commands
    return
  fi

  case "$subcmd" in
    apply)
      case "$prev" in
        --template)
          _describe -t templates 'template' _cv_templates
          return
          ;;
        --lang)
          _describe -t languages 'language' _cv_langs
          return
          ;;
        --color)
          compadd -a _cv_colors
          return
          ;;
      esac

      if [[ "$cur" == -* ]]; then
        _describe -t options 'options' _cv_apply_opts
        return
      fi

      # First positional arg for apply is URL
      _urls
      return
      ;;

    preview)
      case "$prev" in
        --template)
          _describe -t templates 'template' _cv_templates
          return
          ;;
        --role)
          _describe -t roles 'role' _cv_roles
          return
          ;;
        --lang)
          _describe -t languages 'language' _cv_langs
          return
          ;;
        --color)
          compadd -a _cv_colors
          return
          ;;
      esac

      if [[ "$cur" == -* ]]; then
        _describe -t options 'options' _cv_preview_opts
        return
      fi

      # No required positional args for preview
      return
      ;;

    init-profile|init_profile)
      if [[ "$prev" == "--cv" ]]; then
        _files
        return
      fi

      if [[ "$cur" == -* ]]; then
        _describe -t options 'options' _cv_init_profile_opts
        return
      fi

      # Allow file completion as optional positional convenience
      _files
      return
      ;;

    bot|test|help)
      return
      ;;

    *)
      _describe -t commands 'cv command' _cv_commands
      return
      ;;
  esac
}

_cv_from_uv() {
  # Trigger only for: uv run main.py ...
  if [[ "${words[2]-}" == "run" && ( "${words[3]-}" == "main.py" || "${words[3]-}" == "./main.py" ) ]]; then
    local -a saved_words rebuilt
    local saved_current i

    saved_words=("${words[@]}")
    saved_current=$CURRENT

    rebuilt=("cv")
    for (( i = 4; i <= ${#saved_words[@]}; i++ )); do
      rebuilt+=("${saved_words[i]}")
    done

    words=("${rebuilt[@]}")
    (( CURRENT = CURRENT - 3 ))
    (( CURRENT < 2 )) && CURRENT=2

    _cv_complete_core

    words=("${saved_words[@]}")
    CURRENT=$saved_current
    return
  fi

  if (( $+functions[_uv] )); then
    _uv
  else
    _default
  fi
}

_cv_from_python() {
  # Trigger only for: python main.py ...
  if [[ "${words[2]-}" == "main.py" || "${words[2]-}" == "./main.py" ]]; then
    local -a saved_words rebuilt
    local saved_current i

    saved_words=("${words[@]}")
    saved_current=$CURRENT

    rebuilt=("cv")
    for (( i = 3; i <= ${#saved_words[@]}; i++ )); do
      rebuilt+=("${saved_words[i]}")
    done

    words=("${rebuilt[@]}")
    (( CURRENT = CURRENT - 2 ))
    (( CURRENT < 2 )) && CURRENT=2

    _cv_complete_core

    words=("${saved_words[@]}")
    CURRENT=$saved_current
    return
  fi

  if (( $+functions[_python] )); then
    _python
  else
    _default
  fi
}

compdef _cv_complete_core cv
compdef _cv_from_uv uv
compdef _cv_from_python python
compdef _cv_from_python python3
