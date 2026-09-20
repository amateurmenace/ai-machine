# The Constitution Ledger

A signed hash chain over the rules the community adopted.

---

## What it is

Every adopted version of the constitution is a **block**. Each block records
the hash of its own text and the hash of the block before it, so the versions
form a **chain** from the **genesis block** onward. Ratification is an
**N-of-M multi-signature** by named officials, verified rather than asserted.
A block may carry **anchors**: external witnesses proving it existed by a
certain time.

```
  block 1 · v1.1   content f46eaefc   previous 50c95a99   ratified 2 of 3   head
  block 0 · v1.0   content 50c95a99   previous genesis    ratified 2 of 3
```

```bash
python3 -m community.ledger verify
```

Anyone can run that. That is the point.

---

## Can we borrow cryptocurrency vocabulary?

Yes, and I would, because most of it is **literally accurate here** rather than
a metaphor. But the list of words to avoid matters as much as the list to use,
and that is what makes the pitch strong instead of embarrassing.

### Words that are true

| Term | Why it's accurate |
| --- | --- |
| **Hash** | SHA-256 of the canonical text. Exactly what the word means. |
| **Block** | One adopted version plus its header. |
| **Chain** | Each block contains the previous block's hash. That is what a chain is. |
| **Genesis block** | Version 1.0, whose predecessor is the zero hash, by the same convention Bitcoin uses. |
| **Multi-signature / N-of-M** | Ratification literally requires N of M named signers. This is multisig in the ordinary sense. |
| **Ledger** | An append-only record of state changes. Yes. |
| **Anchor** | The standard term for committing a hash to an external timestamped record. |
| **Inclusion proof** | Accurate if you anchor to a transparency log, which returns exactly that. |
| **Fork** | Accurate for another community taking your constitution and diverging. |
| **Tamper-evident** | Precisely what this provides. |

You can say, truthfully: *"Our constitution is a hash chain. Every amendment is
a block signed by a threshold of officials, starting from a genesis block, and
anchored in the town's public record."* Every word of that is checkable against
the code.

### Words to avoid, and why

| Term | Why not |
| --- | --- |
| **Immutable** | The strongest word in the vocabulary and the one that will get you in trouble. An operator with server access can serve different bytes. What you have is **detectable**, not impossible. Use "tamper-evident". |
| **Decentralized** | One organization runs one server. Saying otherwise is simply false. |
| **Consensus** | There is no consensus protocol. There is a vote, by people, in a meeting. That is better, and it has its own name. |
| **Mining, proof of work, gas** | Nothing here does any of it. |
| **Smart contract** | No execution environment, no contracts. |
| **Trustless** | You are asking residents to trust the town. The chain narrows what they have to take on faith; it does not eliminate it. |
| **On-chain / Web3 / DAO** | Imported connotations you do not want on a municipal service, and no accuracy gained. |

### The reason to be this careful

A resident who reads "immutable" and later learns an administrator could swap
the file will trust you **less** than if you had never made the claim. A
guarantee that turns out weaker than advertised costs more than no guarantee.

Precision is also better marketing here. "Tamper-evident, signed by five
officials, and read into the minutes" is a specific, checkable, unusual claim.
"Immutable blockchain constitution" is a phrase people have learned to discount.

### Suggested phrasing

> The rules this assistant follows are kept as a signed chain. Every version is
> a block carrying the hash of its own text and the one before it. Amendments
> are ratified by a threshold of named officials, and the block hash is read
> into the meeting minutes. If anyone changes an adopted version, the chain
> stops verifying and this page says so.

Five sentences, no overclaim, and it does the psychological work you were after.

---

## Why it matters technically

Before this, an answer's provenance recorded `constitution_version: "1.0"`.
A string. Someone could edit `constitution-v1.0.md` to soften a principle and
every answer would still report version 1.0. The log said which rules governed
an answer and could not prove it.

Now provenance carries the content hash. "These rules produced this answer" is
a claim an auditor can check a year later, in the dispute where it matters.

That was the real bug. The chain, the signatures and the anchors are what you
build on top once the binding is right.

---

## The threat model

Worth naming, because it determines how much machinery is warranted.

**Not** a nation-state, a cryptographic attacker, or a malicious operator with
root. Against an operator who controls the server and the repository, nothing
running on that server can save you; only publication outside it can.

**Actually:**

1. A future administrator quietly softening a principle, with no record.
2. A vendor or successor claiming the rules never changed.
3. A dispute a year later about what the assistant was told to do in March.

Hash chain plus signatures plus publication defeats all three. That is why
there is no blockchain here: it would add cost and complexity without
addressing anything on that list.

---

## Using it

### Seal a version

Sealing records what the text **is**. Ratifying, which happens afterwards,
records that the community **adopted** it. Two different acts, and only one of
them is technical.

```bash
python3 -m community.ledger seal 1.1 \
  --status draft --threshold 3 \
  --summary "Adds Principle 21 on drafting public testimony"
```

It prints the block hash. That short hash is what goes into the motion.

### Set up ratifiers

Each ratifier generates a keypair and keeps the private half:

```bash
python3 -m community.ledger keygen --name "A. Chen"
```

Public keys go into `constitution/signers.json`, in a commit, so the roster is
itself part of the record:

```json
{
  "signers": [
    {"name": "A. Chen", "role": "Select Board Chair", "public_key": "ssh-ed25519 AAAA..."},
    {"name": "B. Okafor", "role": "Select Board", "public_key": "ssh-ed25519 AAAA..."}
  ]
}
```

### Ratify

```bash
python3 -m community.ledger sign 1.1 --signer "A. Chen" --key ~/.community-key
```

Below the threshold, the block is not ratified and verification says so.

### Anchor it

```bash
python3 -m community.ledger anchor 1.1 \
  --kind minutes \
  --reference "Select Board minutes 2026-10-14, item 7" \
  --note "Block hash 3f9a2b1c read into the record, approved 5-0"
```

Four kinds are supported: `minutes`, `rekor`, `ots`, `rfc3161`.

**Use `minutes`.** The town clerk's official record is timestamped, legally
meaningful, held outside the operator's control, and it will outlive this
software. It is also the most civically coherent thing you could possibly do:
the institution being served becomes the witness.

Add `rekor` or `ots` if you want a machine-checkable second witness. Neither
costs money. Neither replaces the minutes.

---

## Amending, end to end

1. Copy the current version to the next number. **Never edit an adopted file.**
2. Edit the new file. Add at least one evaluation case that fails before the
   change and passes after it.
3. Seal it as a draft. Open a pull request with the diff, the failing
   transcript that prompted it, and the new test.
4. Public comment period.
5. The board votes. The motion names the block hash.
6. Ratifiers sign. Set the status to adopted.
7. Anchor it in the minutes.
8. Publish evaluation results for the new version beside the old one.

Step 1 is the one people will get wrong, and the ledger catches it: editing an
adopted version breaks verification, and the build fails.

---

## What breaks, and what it looks like

| If someone | Then |
| --- | --- |
| Edits an adopted version | Verification fails naming both hashes. The chat footer shows a red warning. Cloud Build fails. |
| Splices a version out | The next block's link check fails, naming the expected hash. |
| Forges a signature | It does not verify against the roster key. Signing is refused outright. |
| Adds themselves to the roster | The roster is a commit. Diffable, reviewable, and public. |
| Marks a version adopted without enough signatures | Verification reports the shortfall. |

Every one of those has a test in `tests/test_ledger.py`.

---

## Where it shows up

- **Every answer.** Provenance carries the hash, and the transparency panel
  shows `version 1.1 · f46eaefc · ratified`.
- **Every log line.** Which exact rules governed each request.
- **The model's own prompt.** The constitution block opens by naming its version
  and hash.
- **`/community/{town}/constitution/ledger`.** Public, no key.
- **The ledger page in the app.** The chain, the signatures, the anchors, and an
  honest statement of what is not guaranteed.
- **The build.** `cloudbuild.yaml` verifies the chain before deploying.

---

## What it does not do

It does not prove **when** anything happened. Commit dates and file timestamps
are attacker-controlled. Only an external witness fixes that, which is what
anchors are for and why the minutes matter.

It does not stop a determined operator. It makes what they did visible to
anyone who checks.

It does not make the rules good. That is governance, and it is the part that
was always going to be the hard one.
