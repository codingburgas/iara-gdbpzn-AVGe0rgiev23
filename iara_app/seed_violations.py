from app import create_app, db
from app.models import ViolationCategory, ViolationCode, ViolationSeverity

def seed_violation_data():
    app = create_app()
    with app.app_context():
        categories = {
            "Safety": [],
            "Documentation": [],
            "Gear": [],
            "Catch": [],
            "Environmental": [],
        }

        cat_objs = {}
        for name in categories.keys():
            cat = ViolationCategory.query.filter_by(name=name).first()
            if not cat:
                cat = ViolationCategory(name=name)
                db.session.add(cat)
            cat_objs[name] = cat

        db.session.flush()

        codes = [
            ("V-001", "Missing permit", "Vessel is operating without a valid permit.", "Documentation", ViolationSeverity.HIGH),
            ("V-002", "Expired permit", "Permit is expired at time of inspection.", "Documentation", ViolationSeverity.HIGH),
            ("V-003", "Illegal gear", "Use of prohibited fishing gear.", "Gear", ViolationSeverity.CRITICAL),
            ("V-004", "Missing safety equipment", "Required safety equipment not present.", "Safety", ViolationSeverity.HIGH),
            ("V-005", "Unreported catch", "Catch not properly reported.", "Catch", ViolationSeverity.MEDIUM),
        ]

        for code, title, desc, cat_name, severity in codes:
            if not ViolationCode.query.filter_by(code=code).first():
                db.session.add(
                    ViolationCode(
                        code=code,
                        title=title,
                        description=desc,
                        category=cat_objs[cat_name],
                        default_severity=severity.value,
                    )
                )

        db.session.commit()
        print("Violation categories and codes seeded.")


if __name__ == "__main__":
    seed_violation_data()
