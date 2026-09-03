# Mini Shop - Student Starter

Welcome to the Mini Shop software-engineering project.

Your team has inherited a small, incomplete e-commerce application. Your job is not to replace it with a different project. You will study it, find problems, improve its requirements and design, add features, and build a stronger test suite over the course milestones.

The starter is intentionally simple and incomplete. A missing feature is not automatically a bug in the handover—it may be work reserved for a later milestone.

## Technology used

- Python 3.10 or newer
- Flask for routes, sessions, and request handling
- Jinja2 for server-rendered customer and admin pages
- Bootstrap through a CDN for basic responsive styling
- SQLAlchemy for database access
- Pydantic for Python-based form validation
- SQLite for the quickest local setup
- MySQL for the course database
- Pytest for automated tests

No Docker, Node.js, npm, frontend build process, or database migration tool is required.

## Before you begin

Install these tools:

1. [Python](https://www.python.org/downloads/) 3.10 or newer.
2. [Git](https://git-scm.com/downloads).
3. A code editor such as [Visual Studio Code](https://code.visualstudio.com/).
4. MySQL Community Server when your team is ready to use MySQL. SQLite does not require a separate installation.

Check that Python and Git are available:

```bash
python --version
git --version
```

On some macOS or Linux computers, the Python command is `python3` instead of `python`. Use `python3` in every command below if that is what works on your computer.

## Quick start with SQLite

Use SQLite first if you only need to run and inspect the inherited system. SQLite stores the database in one local file and requires no database server.

### 1. Open the project directory

```bash
cd "Course-376-Mini-Shop-Project"
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script, run this once in the same terminal and try again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

When the environment is active, your terminal normally shows `(.venv)`.

### 3. Install the Python packages

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create the tables and sample data

```bash
python seed.py
```

This creates `instance/mini_shop.db`, three sample products, and a development administrator.

### 5. Start the application

```bash
python app.py
```

Open these addresses:

- Storefront: <http://127.0.0.1:8000>
- Health check: <http://127.0.0.1:8000/api/health>
- Admin login: <http://127.0.0.1:8000/admin/login>

Development administrator:

```text
Username: admin
Password: changeme
```

This account is only for local development. Changing the default password and improving account management are part of the project work.

Stop the server by pressing `Ctrl+C` in its terminal.

## Run the tests

Make sure the virtual environment is active, then run:

```bash
pytest
```

The inherited tests are examples, not a complete test suite. Your team must add tests as the system evolves.

## MySQL setup

SQLite is convenient for the handover analysis, but the course SRS identifies MySQL as the final database. Every team member who runs MySQL locally needs MySQL Community Server and the `mysql` command-line client.

### Windows

1. Download the MySQL Community Server MSI from the [official MySQL downloads page](https://dev.mysql.com/downloads/mysql/).
2. Run the installer.
3. Run MySQL Configurator when prompted.
4. Configure MySQL as a Windows service.
5. Set and remember the MySQL `root` password.
6. Open **MySQL Command Line Client** from the Start menu, or open a terminal where the `mysql` command is available.

### macOS

1. Download the MySQL Community Server DMG from the [official MySQL downloads page](https://dev.mysql.com/downloads/mysql/).
2. Open the DMG and run the package installer.
3. Save the temporary/root password shown by the installer.
4. Start MySQL from the MySQL pane in System Settings.

If the `mysql` command is not found, add the standard MySQL binary directory to your shell path:

```bash
echo 'export PATH="/usr/local/mysql/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Ubuntu or Debian Linux

```bash
sudo apt update
sudo apt install mysql-server
sudo systemctl enable --now mysql
sudo mysql_secure_installation
```

Check that the server is running:

```bash
sudo systemctl status mysql
```

### Create the course database and user

Open MySQL as an administrator:

```bash
mysql -u root -p
```

Some Linux installations use this command instead:

```bash
sudo mysql
```

Run the following SQL. You may choose a different development password, but do not use a personal password.

```sql
CREATE DATABASE mini_shop
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER 'mini_shop'@'localhost'
    IDENTIFIED BY 'student_db_password';

GRANT ALL PRIVILEGES ON mini_shop.*
    TO 'mini_shop'@'localhost';

FLUSH PRIVILEGES;
EXIT;
```

### Connect the application to MySQL

Copy the example environment file:

macOS or Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set:

```dotenv
SECRET_KEY=replace-this-with-a-long-random-value
DATABASE_URL=mysql+pymysql://mini_shop:student_db_password@localhost/mini_shop
```

The `PyMySQL` driver is already installed by `requirements.txt`. You do not need to install a separate Python database connector.

Create the MySQL tables and sample data, then start the app:

```bash
python seed.py
python app.py
```

If you receive “Access denied,” check the username and password in `.env`. If you receive “Connection refused,” make sure the MySQL server is running.

Never commit `.env`, a database file, or real passwords to GitHub.

## Resetting local data

For SQLite, stop the server, delete `instance/mini_shop.db`, and run `python seed.py` again.

Resetting MySQL deletes shared data and should only be done with your team’s agreement. Do not drop a team database just to fix one person’s setup problem.

There is no migration system in this starter. When the team changes a SQLAlchemy model, agree on how local development databases will be recreated and record the decision.

## How to make a code change

For each Assignment 4 or Assignment 5 feature:

1. Confirm the requirement ID, backlog item, and acceptance criteria.
2. Create a feature branch.
3. Update the database model and validation model when the feature stores or validates new data.
4. Add or edit Flask routes for the server-side behavior.
5. Add or edit Jinja templates for the customer or administrator interface.
6. Add automated tests for success, invalid input, and unauthorized access when applicable.
7. Run the complete test suite with `pytest`.
8. Open a pull request and request peer review.
9. Update the SRS, diagrams, traceability matrix, backlog, and risk records affected by the change.

Because this starter does not use migrations, model changes require students to recreate their local SQLite database or agree as a team how to update the shared MySQL database. Never reset a shared database without team approval.

## Git and teamwork rules

- Commit the untouched handover before beginning major work.
- Use a feature branch for each backlog item.
- Open pull requests instead of committing features directly to `main`.
- Require a teammate to review meaningful changes.
- Link requirement IDs and backlog items in commits or pull requests.
- Write tests for new or corrected behavior.
- Keep code, tests, requirements, UML, and traceability synchronized.
- Record each member’s individual contributions.

## Project structure

```text
app.py                       easy command for starting Flask
seed.py                      creates tables and sample data
mini_shop/database.py        database engine and sessions
mini_shop/models.py          SQLAlchemy database models
mini_shop/schemas.py         Pydantic validation models
mini_shop/main.py            Flask customer and admin routes
templates/                   server-rendered Jinja pages
static/styles.css            a few project-specific styles
tests/test_app.py            starter automated tests
requirements.txt             Python packages
.env.example                 configuration example
```

Most application behavior belongs in Python. Templates should display data and contain ordinary HTML forms; they should not contain business rules.

## Relationship to the supplied diagrams

The supplied resources remain part of the project handover and use the same Flask terminology as the starter code.

In the supplied sequence diagrams, the lifeline labeled **Flask App** represents the code in `mini_shop/main.py`. The actors, messages, database operations, customer flow, admin flow, and expected behavior apply unless your approved requirements analysis documents a correction.

## Common problems

**`python` is not recognized**  
Install Python and select the installer option that adds Python to your PATH. On macOS/Linux, try `python3`.

**`ModuleNotFoundError`**  
Activate `.venv` and run `python -m pip install -r requirements.txt`.

**The catalog is empty**  
Stop the server and run `python seed.py` using the same `.env` configuration.

**The page has no styling**  
Bootstrap is loaded from a CDN. Check your internet connection. Core application behavior should still work without the stylesheet.

**MySQL says access denied**  
Check the database username, password, and privileges. Confirm that `.env` contains the same values.

**MySQL connection is refused**  
Start the MySQL service and confirm it is listening on the default local port.

**Port 8000 is already in use**  
Stop the other application using the port, or run `flask --app mini_shop.main run --debug --port 8001` and open port 8001.
