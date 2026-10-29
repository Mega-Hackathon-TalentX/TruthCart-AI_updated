TruthCart AI — Multiple Debug Datasets

All generated product records are synthetic test fixtures, not real retail facts.

Files:
1. truthcart_products_5000.csv — clean baseline catalogue, 5,000 rows.
2. truthcart_demo_policies.csv — grounding and policy rules.
3. truthcart_evaluation_questions_150.csv — answer/clarify/refuse evaluation prompts.
4. truthcart_evaluation_questions_150.jsonl — same prompts in JSON Lines format.
5. truthcart_retrieval_filter_tests_100.csv — 100 retrieval, exact lookup, numeric and filtering tests.
6. truthcart_edge_cases_validation.csv — intentionally malformed/inconsistent rows for validation tests.
7. truthcart_policy_faq_gold_answers.csv — FAQ prompts and expected safe answers.
8. truthcart_conversation_multilingual_tests.csv — multi-turn, multilingual, citation, context, and prompt-injection tests.
9. truthcart_test_results_template.csv — blank template to log actual app results.

Suggested order:
A. Upload only the clean baseline catalogue to a dev/staging environment.
B. Run the 150 evaluation prompts and 100 retrieval/filter tests.
C. Test policy FAQ grounding.
D. Upload edge-case rows only in a disposable test environment; some rows are intentionally invalid.
E. Test conversations and multilingual behavior.
F. Log runs in the results template.

Map columns explicitly if the app schema differs. Back up your database and never mix edge-case rows into the clean baseline catalogue.
