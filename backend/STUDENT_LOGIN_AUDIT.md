# Student Login Account Creation — Audit & Dry-Run

## Summary

**Status:** All Year 6 students exist in the database but have NO user accounts/login credentials.

**Action:** Create logins using safe dry-run → approve → real-write pattern (same as teacher password script).

## Audit Findings

### Year 6 Student Population

| Metric | Count |
|--------|-------|
| Total Year 6 students | 35 |
| Students WITH user accounts linked | 0 |
| Students available for account creation | 35 |

### Sample Available Students

```
Email                                           | Name
abebi.olagoke@student.fairview-school.ng       | Abebi Olagoke
aida.abioye@student.fairview-school.ng         | Aida Abioye
blessing.bello@student.fairview-school.ng      | Blessing Bello
zainab.obi@student.fairview-school.ng          | Zainab Obi
[... 31 more ...]
```

## Usage Instructions

### Step 1: List all available Year 6 candidates

```bash
python scripts/create_student_login_dryrun.py --list-year-6
```

Output shows:
- All 35 Year 6 students
- Their email addresses
- Their student IDs in the database

### Step 2: Dry-run for a specific student

```bash
python scripts/create_student_login_dryrun.py "zainab.obi@student.fairview-school.ng"
```

Output shows:
- Student name, email, ID, class
- Organization
- What will be created (account details)
- Confirmation that password will be randomly generated and printed to terminal only

**Review this output carefully before proceeding.**

### Step 3: Create the account (real write)

Once you approve the dry-run:

```bash
python scripts/create_student_login_real.py "zainab.obi@student.fairview-school.ng"
```

Output:
- Confirms account created successfully
- **Prints password to terminal ONLY** (never stored in git or any file)
- Password never appears in logs or database

### Step 4: Student can now log in

- Email: `zainab.obi@student.fairview-school.ng`
- Password: [the one printed in step 3]
- After first login, student can change password in account settings

## Safety Notes

✅ **Dry-run script is read-only** — no database changes
✅ **Real script prints password to terminal only** — never committed
✅ **Each student gets unique random password** (16 chars, mixed case/digits/symbols)
✅ **Account is immediately active** — student can log in right away
✅ **Idempotent dry-run** — can run multiple times safely

## Testing the CBT → Report Flow

Once student has login:
1. Log in as the student with their password
2. Navigate to CBT (Cbt module)
3. Find and sit the exam created by mathematics@ teacher
4. Submit answers
5. Verify score appears in student's report card (Make Report)

## Troubleshooting

**"No student found with email"**
- Check the email is spelled correctly (case-insensitive)
- Run `--list-year-6` to see available emails

**"Student already has a user account"**
- This student has already been provisioned
- Use a different student email

**"student role not found in org"**
- This should not happen (bootstrap creates all system roles)
- Contact support or check database directly
