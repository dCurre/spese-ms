"""
Test that the new backend balance logic produces the same results as the old frontend logic.

Old frontend logic (TypeScript, saldo-details.component.ts / expenses-list-details.component.ts):
  mapPagato = { "Nome Cognome": total_amount }
  for each (buyer, receiver) pair where buyer != receiver:
    toPay = (receiverPaid - buyerPaid) / mapPagato.size

New backend logic (Python, routes.py get_expenses_list_balance):
  map_pagato = { "Nome Cognome": total_amount }
  for each (buyer, receiver) pair where buyer != receiver:
    toPay = round((receiver_paid - buyer_paid) / len(map_pagato), 2)

Key difference: old TS uses `${name} ${surname ?? ''}` (no trim, trailing space when no surname)
               new Python uses f"{name} {surname or ''}".strip() (trimmed)
Both produce identical amounts; only display key may differ by trailing space for guests.
"""

def old_frontend_compute_balance(expenses):
    """Replicates the old TypeScript computeBalance logic.
    TypeScript: `${e.owner.name} ${e.owner.surname ?? ''}` (no .trim())
    Produces trailing space when surname is null/undefined.
    """
    map_pagato = {}
    for e in expenses:
        surname = e.get('owner_surname') or ''   # replicates `?? ''`
        buyer = f"{e['owner_name']} {surname}"   # no strip -- matches TS template literal
        map_pagato[buyer] = map_pagato.get(buyer, 0) + float(e['amount'])

    balance = []
    for buyer, buyer_paid in map_pagato.items():
        for receiver, receiver_paid in map_pagato.items():
            if buyer != receiver:
                balance.append({
                    "buyer": buyer,
                    "receiver": receiver,
                    "toPay": (receiver_paid - buyer_paid) / len(map_pagato),
                })
    return balance, map_pagato


def new_backend_compute_balance(expenses):
    """Replicates the new Python backend logic from routes.py."""
    map_pagato = {}
    for e in expenses:
        key = f"{e['owner_name']} {e.get('owner_surname') or ''}".strip()
        map_pagato[key] = map_pagato.get(key, 0) + float(e['amount'])

    balance = []
    for buyer, buyer_paid in map_pagato.items():
        for receiver, receiver_paid in map_pagato.items():
            if buyer != receiver:
                balance.append({
                    "buyer": buyer,
                    "receiver": receiver,
                    "toPay": round((receiver_paid - buyer_paid) / len(map_pagato), 2),
                })
    totals = [{"name": k, "amount": round(v, 2)} for k, v in sorted(map_pagato.items())]
    return balance, totals


def run_test(name, expenses):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Spese input: {expenses}")

    old_balance, old_map = old_frontend_compute_balance(expenses)
    new_balance, new_totals = new_backend_compute_balance(expenses)

    # Compare maps (strip keys to normalize trailing spaces from null surnames)
    old_map_norm = {k.strip(): v for k, v in old_map.items()}
    new_map = {t['name']: t['amount'] for t in new_totals}
    print(f"\nmap_pagato (vecchio, normalizzato): {old_map_norm}")
    print(f"totals (nuovo):                     {new_map}")
    assert set(old_map_norm.keys()) == set(new_map.keys()), \
        f"Keys differ: {set(old_map_norm.keys())} != {set(new_map.keys())}"
    for k in old_map_norm:
        assert abs(old_map_norm[k] - new_map[k]) < 0.01, \
            f"Amount differs for {k}: {old_map_norm[k]} vs {new_map[k]}"
    print("OK map_pagato / totals corrispondono")

    # Compare balance entries (normalize keys, sort by buyer+receiver)
    old_norm = [{"buyer": b['buyer'].strip(), "receiver": b['receiver'].strip(), "toPay": b['toPay']}
                for b in old_balance]
    old_sorted = sorted(old_norm, key=lambda x: (x['buyer'], x['receiver']))
    new_sorted = sorted(new_balance, key=lambda x: (x['buyer'], x['receiver']))

    assert len(old_sorted) == len(new_sorted), \
        f"Balance count differs: {len(old_sorted)} vs {len(new_sorted)}"
    for i, (o, n) in enumerate(zip(old_sorted, new_sorted)):
        assert o['buyer'] == n['buyer'], \
            f"[{i}] buyer differs: '{o['buyer']}' vs '{n['buyer']}'"
        assert o['receiver'] == n['receiver'], \
            f"[{i}] receiver differs: '{o['receiver']}' vs '{n['receiver']}'"
        # New backend rounds to 2 decimals; compare with tolerance
        diff = abs(o['toPay'] - n['toPay'])
        assert diff < 0.01, \
            f"[{i}] toPay differs {o['buyer']}->{o['receiver']}: {o['toPay']} vs {n['toPay']} (diff={diff})"

    print(f"\nBalance entries ({len(old_sorted)} righe):")
    for o, n in zip(old_sorted, new_sorted):
        match = "OK" if abs(o['toPay'] - n['toPay']) < 0.01 else "DIFF"
        print(f"  [{match}] {o['buyer']} -> {o['receiver']}: vecchio={o['toPay']:.2f}  nuovo={n['toPay']:.2f}")
    print("OK balance corrispondono")


# Test 1: 2 partecipanti, spese bilanciate
run_test(
    "2 partecipanti, spese bilanciate",
    [
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 50},
        {"owner_name": "Luigi", "owner_surname": "Verdi", "amount": 50},
    ]
)

# Test 2: 2 partecipanti, spese sbilanciate
run_test(
    "2 partecipanti, spese sbilanciate",
    [
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 80},
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 20},
        {"owner_name": "Luigi", "owner_surname": "Verdi", "amount": 30},
    ]
)

# Test 3: 3 partecipanti
run_test(
    "3 partecipanti",
    [
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 90},
        {"owner_name": "Luigi", "owner_surname": "Verdi", "amount": 30},
        {"owner_name": "Anna", "owner_surname": "Bianchi", "amount": 60},
    ]
)

# Test 4: partecipante senza cognome (es. ospite)
run_test(
    "Ospite senza cognome",
    [
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 100},
        {"owner_name": "Ospite", "owner_surname": None, "amount": 40},
    ]
)

# Test 5: 4 partecipanti con importi decimali
run_test(
    "4 partecipanti con decimali",
    [
        {"owner_name": "Alice", "owner_surname": None, "amount": 33.33},
        {"owner_name": "Bob", "owner_surname": None, "amount": 25.50},
        {"owner_name": "Carlo", "owner_surname": None, "amount": 41.17},
        {"owner_name": "Diana", "owner_surname": None, "amount": 10.00},
    ]
)

# Test 6: nessuna spesa
run_test(
    "Nessuna spesa",
    []
)

# Test 7: stesso partecipante con multiple spese
run_test(
    "Multiple spese stesso partecipante",
    [
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 10},
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 20},
        {"owner_name": "Mario", "owner_surname": "Rossi", "amount": 30},
        {"owner_name": "Luigi", "owner_surname": "Verdi", "amount": 25},
        {"owner_name": "Luigi", "owner_surname": "Verdi", "amount": 25},
    ]
)

print(f"\n{'='*60}")
print("TUTTI I TEST SUPERATI -- logica backend = logica frontend")
print(f"{'='*60}\n")
