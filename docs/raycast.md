# Raycast setup

## What you get

The **Query JSONL Vault** Script Command accepts any natural-language query and shows a bounded
Markdown evidence result. It is not limited to people or entity fields. Missing and partial results
remain visible; unavailable or stale runtimes fail clearly.

## Configure the private runtime

Create this local file outside the repository:

```json
{
  "runtime": "/path/to/jsonl-vault/default"
}
```

Save it as `~/.config/quick-vault-retriever/config.json`. Alternatively set
`QUICK_VAULT_RUNTIME` in the environment that launches the script.

## Add the command

1. Open Raycast Settings.
2. Select **Extensions → Script Commands**.
3. Add this repository's `raycast/` directory.
4. Invoke **Query JSONL Vault** and enter a question.

The script first uses an installed `quick-vault` command. Otherwise it finds `uv` and runs the
repository environment directly. It contains no runtime path, search SQL, network call, or vault
mutation. The Script Commands directory may contain a symlink to `raycast/query-vault.sh`; the
launcher resolves that symlink before locating the repository, so it does not depend on Raycast's
working directory.

## Result states

- **Evidence:** one or more records cover every meaningful query term.
- **Partial evidence:** records matched, but no single record covered the complete query.
- **No evidence found:** the fresh index returned no matches.
- **Stale/Unavailable/Invalid request:** fix the local runtime or configuration before trusting a
  result.

Raycast output can contain private snippets. Do not share screenshots or copy output into cloud
tools without making that disclosure decision explicitly.
