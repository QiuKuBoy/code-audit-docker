# SQL Injection Audit Skill

## Overview
SQL Injection occurs when user-supplied input is concatenated into SQL queries without proper sanitization or parameterization.

## Audit Methodology
1. **Find all database query points**: Search for execute(), query(), raw(), text() calls
2. **Trace input origin**: For each query, trace backwards to find where the input comes from
3. **Check parameterization**: Verify if parameterized queries / ORM methods are used
4. **Test bypass scenarios**: Check for ORM raw methods, string formatting in queries

## Common Patterns by Language

### Python
- `cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")` — f-string injection
- `cursor.execute("SELECT * FROM users WHERE id = " + user_id)` — string concat
- `db.engine.execute(text(f"SELECT * FROM {table}"))` — SQLAlchemy text()
- `User.objects.raw(f"WHERE name = '{name}'")` — Django raw()
- `.format()` and `%` formatting in SQL strings

### Java
- `Statement.executeQuery("SELECT * FROM users WHERE id = " + id)` — Statement concat
- `@Query("SELECT u FROM User WHERE u.name = '" + name + "'")` — JPQL concat
- MyBatis `${param}` (not `#{param}`) — direct substitution
- `String.format("SELECT ... WHERE id = %s", id)` — format injection

### Node.js
- `db.query("SELECT * FROM users WHERE id = " + req.params.id)` — string concat
- `sequelize.query("SELECT * FROM users WHERE name = '" + name + "'")` — raw query
- Template literals in SQL: `` `SELECT * FROM users WHERE id = ${id}` ``

### Go
- `db.Query("SELECT * FROM users WHERE id = " + id)` — string concat
- `fmt.Sprintf("SELECT ... WHERE name = '%s'", name)` — Sprintf injection

## Key Reminders
- ORM does NOT guarantee safety: raw(), text(), execute() can still inject
- Stored procedures can have injection if they use dynamic SQL
- ORDER BY / LIMIT clauses can't always be parameterized — check separately
- Second-order injection: data from database used in another query
