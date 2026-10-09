# TA meeting and Iteration 2 follow-up — 2026-10-07

[English](2026-10-07-ta-and-iteration-2.md) · [한국어](2026-10-07-ta-and-iteration-2.ko.md)

Source: Iteration 1 PM's summary of the TA meeting and team follow-up. Items marked **proposal** were discussed but not yet implemented or finalized.

## TA feedback

- Keep the schedule granular. Add new work as `A1`, `A2`, etc. without renumbering existing `P` tasks; list only actual participants and workers.
- Track team meetings and decisions so later PMs can reconstruct why the project changed.
- Make the difference from generic recipe apps concrete: easy ingredient registration and recommendations tailored to a person living alone.
- Check the tradeoff between registration convenience and accuracy. Try practical alternatives when recognition quality is uncertain.
- Complete enough of the single-person recommendation flow that the project purpose is visible.
- Consider proactive suggestions such as an additional ingredient that unlocks more dishes.

## Team follow-up and proposed behavior

| Topic | Discussion | State |
| --- | --- | --- |
| Serving size and tools | Curate recipes and quantities for one person; connect recipes to required cooking tools. | Iteration 2 data/product work |
| Refresh | Offer another feasible recipe when a user dislikes a result, following the filtered order. | Proposal; ranking details open |
| AI substitution | Consider limited ingredient and serving changes for similar ingredients; show when an unavailable ingredient would enable a recipe. The server would send the adapted result to the client. | Proposal; boundaries and validation open |
| Server flow 1 | Receive a photo, analyze it, return candidate ingredient names for user confirmation. | Direction agreed; API pending |
| Server flow 2 | Receive confirmed fridge contents and user constraints; return feasible recipes from the DB. | Direction agreed; API pending |
| User profile | Include allergies, cooking tools, and ingredients as recommendation inputs. | Data contract pending |
| Seasonings | Consider a checklist for commonly held seasonings that fridge photos may not reveal. | Option to evaluate |

## Next actions

1. Specify the two API contracts and mock replacement sequence with Android and server owners.
2. Choose a small pilot recipe set and record one-person serving, tool, allergen, and missing-ingredient rules.
3. Run a limited real-photo recognition study; document correction burden and fallback entry paths.
4. Write safe boundaries for AI recipe adjustment and distinguish original source content from generated changes.
5. Keep the schedule, decision log, and Wiki aligned as these choices are resolved.
