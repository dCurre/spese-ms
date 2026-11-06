# scripts/

## Bump automatico della versione

Il repo usa un **bump automatico della patch** a ogni `git push`, tramite un hook
`pre-push` versionato (`scripts/hooks/pre-push`), attivato via `core.hooksPath`.

### Come funziona

A ogni `git push`:

1. L'hook controlla i commit in uscita.
2. Se il file `VERSION` è già cambiato in quei commit → non fa nulla (niente doppio bump).
3. Altrimenti incrementa la patch di `VERSION` (`MAJOR.MINOR.PATCH` → `...PATCH+1`),
   la aggiunge all'ultimo commit con `git commit --amend`, annulla il push corrente
   e rilancia da solo il push del commit aggiornato.

Risultato: **un solo `git push` da parte tua → un solo push a GitHub → una sola build**,
senza commit "bump" separati.

> ⚠️ Al termine vedrai `error: failed to push some refs`. È **atteso e corretto**:
> è l'hook che blocca il push vecchio dopo aver spinto quello aggiornato. Non è un bug.

### Attivazione (una tantum, dopo un clone)

L'hook è versionato ma `core.hooksPath` è una config **locale** non versionata. Dopo un
clone va attivato una volta:

```bash
git config core.hooksPath scripts/hooks
```

### Il file VERSION

- `VERSION` (nella root) è l'**unica fonte di verità** della versione.
- `version.py` legge da `VERSION` ed espone `__version__` all'app.
- **Non bumpare `VERSION` a mano**: ci pensa l'hook.

### CI

Il workflow GitHub Actions (`.github/workflows/deploy.yml`) **non bumpa** più la versione:
si limita a **leggere** `VERSION`. Questo evita il doppio incremento.
