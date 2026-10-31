# Résumé du projet

**AuthFlow Lab — Implémentation OAuth/OIDC et tests de sécurité** est un projet local de portfolio destiné à illustrer les compétences en développement Python, compréhension des protocoles d'identité et validation de sécurité dans le cadre d'une candidature PFE.

Le laboratoire comprend un serveur d'autorisation Flask, un client web confidentiel et une API séparée. Le flux Authorization Code utilise PKCE S256, une comparaison exacte des URI de redirection et une consommation atomique des codes dans PostgreSQL. Un sous-ensemble documenté d'OpenID Connect ajoute des ID tokens signés, la découverte et un endpoint JWKS.

Le client valide state et nonce, conserve les tokens côté serveur et utilise des cookies sécurisés. L'API vérifie la signature, l'émetteur, l'audience, l'expiration, le type du token, la révocation du grant et les scopes. Les primitives cryptographiques et le hachage Argon2id proviennent de bibliothèques maintenues.

La suite pytest couvre les chemins positifs et les rejets : rejeu, expiration, mauvais client, PKCE incorrect, substitution d'ID token, erreurs de signature et de claims. Un test concurrent utilise réellement PostgreSQL. Des tests Chromium et un client indépendant Authlib complètent la validation. Docker Compose fournit l'environnement HTTPS local, et GitHub Actions définit les contrôles automatisés sans identifiants cloud.

Il s'agit d'une **implémentation pédagogique limitée**, pas d'un fournisseur d'identité de production ni d'un produit certifié OIDC. Les résultats réellement observés, les limites et les tests bloqués sont consignés dans `test-results.md`. Aucune découverte de vulnérabilité nouvelle n'est revendiquée.

Formulation possible pour le CV, à adapter aux résultats observés : « Développement d'un laboratoire OAuth 2.0/OIDC en Python/Flask avec PostgreSQL, PKCE S256, validation JWT et tests de sécurité automatisés, dont un test de rejeu concurrent et une vérification d'interopérabilité. »
