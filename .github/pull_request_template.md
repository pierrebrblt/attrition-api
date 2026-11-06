## Objet

<!-- Que change cette PR et pourquoi ? Lien vers l'issue éventuelle. -->

## Type

- [ ] feat : nouvelle fonctionnalité
- [ ] fix : correction
- [ ] docs / test / ci / refactor / chore

## Checklist avant fusion

- [ ] La CI est verte (lint, tests PostgreSQL, docs)
- [ ] Couverture ≥ 90 %
- [ ] Tests ajoutés pour les nouveaux cas (nominal + erreurs)
- [ ] Documentation / README mis à jour
- [ ] Si le modèle change : `models/metrics.json` régénéré et seuils de `docs/model.md` respectés
- [ ] Si le schéma change : `db/schema.sql` régénéré (`python -m db.create_db --dump-sql db/schema.sql`)
- [ ] Aucun secret dans le code
