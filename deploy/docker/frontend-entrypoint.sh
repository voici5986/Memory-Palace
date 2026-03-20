#!/usr/bin/env sh
set -eu

template_path="/etc/nginx/templates/default.conf.template"
target_path="/etc/nginx/conf.d/default.conf"

mcp_api_key="${MCP_API_KEY:-}"
carriage_return="$(printf '\r')"

# POSIX shell variables cannot preserve NUL bytes. Reject the remaining
# control characters that can break the generated nginx config.
case "${mcp_api_key}" in
  *"$carriage_return"*|*'
'*)
    echo "MCP_API_KEY contains unsupported control characters." >&2
    exit 1
    ;;
esac

escaped_mcp_api_key="$(printf '%s' "${mcp_api_key}" | sed 's/[\\\"$]/\\&/g')"
export MCP_API_KEY_NGINX_ESCAPED="${escaped_mcp_api_key}"

envsubst '${MCP_API_KEY_NGINX_ESCAPED}' < "${template_path}" > "${target_path}"
nginx -t

exec nginx -g 'daemon off;'
