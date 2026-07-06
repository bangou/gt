from gto.importer import import_csv_to_db, init_db


def test_import_csv_to_db_populates_flat_table_and_ignores_duplicates(tmp_path):
    db_path = tmp_path / "gto_solver.db"
    csv_path = tmp_path / "gto_data.csv"
    csv_path.write_text(
        "\n".join(
            [
                "table_size,position,effective_stack_bb,street,hand_key,board_texture_key,action_history_key,action,size_bb,probability,source,notes",
                "9,BTN,100,preflop,AKs,none,RFI,raise,2.5,100.0,Upswing,",
                "9,BTN,100,preflop,AKs,none,RFI,raise,2.5,100.0,Upswing,",
                "9,BTN,100,preflop,AKs,none,RFI,fold,,0.0,Upswing,",
            ]
        ),
        encoding="utf-8",
    )

    connection = init_db(db_path)
    try:
        inserted_rows = import_csv_to_db(connection, csv_path)
        count = connection.execute("SELECT COUNT(*) FROM gto_strategies").fetchone()[0]
    finally:
        connection.close()

    assert inserted_rows == 2
    assert count == 2
