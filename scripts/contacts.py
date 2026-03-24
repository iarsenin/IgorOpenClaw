#!/usr/bin/env python3
"""Apple Contacts reader for OpenClaw agent.

Reads from the local macOS AddressBook SQLite databases (all sources:
iCloud, Google, Exchange, etc.). Requires Full Disk Access for python3.

Usage:
    contacts.py search <query>              Search by name, phone, email, or org
    contacts.py get <name-or-number>        Get full details for a contact
    contacts.py list [--limit N]            List all contacts (alphabetical)
"""

import sqlite3
import sys
import os
import glob
import re

AB_DIR = os.path.expanduser(
    "~/Library/Application Support/AddressBook"
)


def _open_all_dbs():
    """Open all AddressBook SQLite databases (main + sources)."""
    pattern = os.path.join(AB_DIR, "**", "AddressBook-v22.abcddb")
    paths = glob.glob(pattern, recursive=True)
    dbs = []
    for p in paths:
        try:
            db = sqlite3.connect(p)
            db.row_factory = sqlite3.Row
            dbs.append(db)
        except Exception:
            pass
    return dbs


def _query_contacts(dbs, where_clause, params):
    """Query contacts across all databases, deduplicate by full number."""
    results = {}
    for db in dbs:
        try:
            c = db.cursor()
            c.execute(f"""
                SELECT r.Z_PK, r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION,
                       r.ZNICKNAME, r.ZJOBTITLE, r.ZDEPARTMENT
                FROM ZABCDRECORD r
                WHERE {where_clause}
            """, params)
            for row in c.fetchall():
                pk = row["Z_PK"]
                key = (row["ZFIRSTNAME"] or "", row["ZLASTNAME"] or "")
                contact = {
                    "first": row["ZFIRSTNAME"] or "",
                    "last": row["ZLASTNAME"] or "",
                    "org": row["ZORGANIZATION"] or "",
                    "nickname": row["ZNICKNAME"] or "",
                    "title": row["ZJOBTITLE"] or "",
                    "phones": [],
                    "emails": [],
                }
                c2 = db.cursor()
                c2.execute(
                    "SELECT ZFULLNUMBER, ZLABEL FROM ZABCDPHONENUMBER WHERE ZOWNER=?",
                    (pk,),
                )
                for p in c2.fetchall():
                    if p["ZFULLNUMBER"]:
                        contact["phones"].append(
                            (p["ZFULLNUMBER"], _label(p["ZLABEL"]))
                        )
                c2.execute(
                    "SELECT ZADDRESS, ZLABEL FROM ZABCDEMAILADDRESS WHERE ZOWNER=?",
                    (pk,),
                )
                for e in c2.fetchall():
                    if e["ZADDRESS"]:
                        contact["emails"].append(
                            (e["ZADDRESS"], _label(e["ZLABEL"]))
                        )
                name_key = f"{contact['first']} {contact['last']}".strip()
                if name_key not in results or len(contact["phones"]) > len(
                    results[name_key]["phones"]
                ):
                    results[name_key] = contact
        except Exception:
            pass
    return list(results.values())


def _label(raw):
    """Clean up Apple's internal label format."""
    if not raw:
        return ""
    raw = raw.replace("_$!<", "").replace(">!$_", "")
    return raw


def _normalize_phone(number):
    """Strip a phone number to digits only for comparison."""
    return re.sub(r"[^\d+]", "", number)


def cmd_search(query):
    dbs = _open_all_dbs()
    if not dbs:
        print("ERROR: No AddressBook databases found. Check Full Disk Access.")
        return
    try:
        q = f"%{query}%"
        digits = _normalize_phone(query)
        # Name/org/email search via SQL, phone search in Python (handles Unicode hyphens)
        contacts = _query_contacts(
            dbs,
            """(r.ZFIRSTNAME LIKE ? OR r.ZLASTNAME LIKE ?
                OR r.ZORGANIZATION LIKE ? OR r.ZNICKNAME LIKE ?
                OR r.Z_PK IN (
                    SELECT ZOWNER FROM ZABCDEMAILADDRESS WHERE ZADDRESS LIKE ?
                ))""",
            (q, q, q, q, q),
        )
        # Also search by phone digits (can't do in SQL due to Unicode hyphens)
        if digits and len(digits) >= 4:
            phone_contacts = _query_contacts(dbs, "1=1", ())
            for c in phone_contacts:
                for phone, _ in c["phones"]:
                    if digits in _normalize_phone(phone):
                        name_key = f"{c['first']} {c['last']}".strip()
                        if not any(
                            f"{x['first']} {x['last']}".strip() == name_key
                            for x in contacts
                        ):
                            contacts.append(c)
                        break
        if not contacts:
            print(f"No contacts matching: {query}")
            return
        print(f"--- {len(contacts)} contact(s) matching '{query}' ---\n")
        for c in sorted(contacts, key=lambda x: (x["last"], x["first"])):
            _print_contact(c)
    finally:
        for db in dbs:
            db.close()


def cmd_get(identifier):
    dbs = _open_all_dbs()
    if not dbs:
        print("ERROR: No AddressBook databases found. Check Full Disk Access.")
        return
    try:
        q = f"%{identifier}%"
        digits = _normalize_phone(identifier)
        contacts = _query_contacts(
            dbs,
            """(r.ZFIRSTNAME || ' ' || COALESCE(r.ZLASTNAME,'') LIKE ?
                OR r.Z_PK IN (
                    SELECT ZOWNER FROM ZABCDPHONENUMBER WHERE ZFULLNUMBER LIKE ?
                ))""",
            (q, f"%{digits}%" if digits else q),
        )
        if not contacts:
            print(f"No contact found for: {identifier}")
            return
        for c in contacts:
            _print_contact(c, verbose=True)
    finally:
        for db in dbs:
            db.close()


def cmd_list(limit=50):
    dbs = _open_all_dbs()
    if not dbs:
        print("ERROR: No AddressBook databases found. Check Full Disk Access.")
        return
    try:
        contacts = _query_contacts(
            dbs,
            "r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL",
            (),
        )
        contacts.sort(key=lambda x: (x["last"].lower(), x["first"].lower()))
        print(f"{'Name':<30} {'Phone':<20} {'Email'}")
        print("-" * 80)
        for c in contacts[:limit]:
            name = f"{c['first']} {c['last']}".strip()
            if c["org"] and not name:
                name = c["org"]
            phone = c["phones"][0][0] if c["phones"] else ""
            email = c["emails"][0][0] if c["emails"] else ""
            print(f"{name:<30} {phone:<20} {email}")
        if len(contacts) > limit:
            print(f"\n... and {len(contacts) - limit} more (use --limit N)")
    finally:
        for db in dbs:
            db.close()


def _print_contact(c, verbose=False):
    name = f"{c['first']} {c['last']}".strip()
    if c["nickname"]:
        name += f" ({c['nickname']})"
    print(f"  {name}")
    if c["org"]:
        org = c["org"]
        if c["title"]:
            org = f"{c['title']}, {org}"
        print(f"    org: {org}")
    for phone, label in c["phones"]:
        lbl = f" [{label}]" if label else ""
        print(f"    phone: {phone}{lbl}")
    for email, label in c["emails"]:
        lbl = f" [{label}]" if label else ""
        print(f"    email: {email}{lbl}")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    limit = 50
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            filtered.append(args[i])
            i += 1
    args = filtered

    if cmd == "search":
        if not args:
            print("Usage: contacts.py search <query>")
            sys.exit(1)
        cmd_search(" ".join(args))
    elif cmd == "get":
        if not args:
            print("Usage: contacts.py get <name-or-number>")
            sys.exit(1)
        cmd_get(" ".join(args))
    elif cmd == "list":
        cmd_list(limit)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
