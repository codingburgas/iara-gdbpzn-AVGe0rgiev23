# routes/lookup.py
# ---------------------------------------------------------
# Lookup / Reference-data management routes (admin only):
#   - Species catalogue
#   - Gear type catalogue
#   - Violation categories & codes (replaces seed-only workflow)
# ---------------------------------------------------------

import csv
import io
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort
)
from flask_login import login_required, current_user

from .. import db
from ..models import Species, GearType, ViolationCategory, ViolationCode
from ..forms import (
    SpeciesForm, GearTypeForm,
    ViolationCategoryForm, ViolationCodeForm,
    SpeciesCSVImportForm
)
from ..decorators import admin_required
from ..utils import log_action

bp = Blueprint("lookup", __name__, url_prefix="/admin/lookup")


# ══════════════════════════════════════════════════════════════
#  SPECIES
# ══════════════════════════════════════════════════════════════

@bp.route("/species")
@login_required
@admin_required
def species_list():
    q           = request.args.get("q", "").strip()
    protected_f = request.args.get("protected", "")
    page        = request.args.get("page", 1, type=int)
    per_page    = 20

    query = Species.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Species.name_bg.ilike(like),
                Species.name_en.ilike(like),
                Species.scientific_name.ilike(like),
            )
        )
    if protected_f == "yes":
        query = query.filter_by(is_protected=True)
    elif protected_f == "no":
        query = query.filter_by(is_protected=False)

    pagination = query.order_by(Species.name_bg).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "lookup/species_list.html",
        species=pagination.items,
        pagination=pagination,
        q=q,
        protected_f=protected_f,
        total=Species.query.count(),
        protected_count=Species.query.filter_by(is_protected=True).count(),
        title="Species Catalogue"
    )


@bp.route("/species/<int:species_id>")
@login_required
@admin_required
def species_detail(species_id):
    sp = db.get_or_404(Species, species_id)
    return render_template(
        "lookup/species_detail.html",
        sp=sp,
        title=f"Species — {sp.name_bg}"
    )


@bp.route("/species/add", methods=["GET", "POST"])
@login_required
@admin_required
def species_add():
    form = SpeciesForm()
    if form.validate_on_submit():
        if Species.query.filter(
            db.func.lower(Species.name_bg) == form.name_bg.data.strip().lower()
        ).first():
            flash("A species with this Bulgarian name already exists.", "danger")
        else:
            sp = Species(
                name_bg         = form.name_bg.data.strip(),
                name_en         = form.name_en.data.strip() or None,
                scientific_name = form.scientific_name.data.strip() or None,
                min_size_cm     = form.min_size_cm.data,
                max_size_cm     = form.max_size_cm.data,
                season_start    = form.season_start.data or None,
                season_end      = form.season_end.data or None,
                daily_limit_kg  = form.daily_limit_kg.data,
                is_protected    = form.is_protected.data,
                notes           = form.notes.data or None,
            )
            db.session.add(sp)
            db.session.commit()
            log_action("species_created", "Species", sp.id, f"Name: {sp.name_bg}")
            flash(f"Species '{sp.name_bg}' added successfully.", "success")
            return redirect(url_for("lookup.species_detail", species_id=sp.id))

    return render_template(
        "lookup/species_form.html",
        form=form,
        edit=False,
        title="Add Species"
    )


@bp.route("/species/<int:species_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def species_edit(species_id):
    sp   = db.get_or_404(Species, species_id)
    form = SpeciesForm(obj=sp)

    if form.validate_on_submit():
        dup = Species.query.filter(
            db.func.lower(Species.name_bg) == form.name_bg.data.strip().lower(),
            Species.id != sp.id
        ).first()
        if dup:
            flash("Another species already uses that Bulgarian name.", "danger")
        else:
            old_name         = sp.name_bg
            sp.name_bg         = form.name_bg.data.strip()
            sp.name_en         = form.name_en.data.strip() or None
            sp.scientific_name = form.scientific_name.data.strip() or None
            sp.min_size_cm     = form.min_size_cm.data
            sp.max_size_cm     = form.max_size_cm.data
            sp.season_start    = form.season_start.data or None
            sp.season_end      = form.season_end.data or None
            sp.daily_limit_kg  = form.daily_limit_kg.data
            sp.is_protected    = form.is_protected.data
            sp.notes           = form.notes.data or None
            sp.updated_at      = datetime.utcnow()
            db.session.commit()
            log_action("species_edited", "Species", sp.id,
                       f"Name: {old_name} → {sp.name_bg}")
            flash(f"Species '{sp.name_bg}' updated.", "success")
            return redirect(url_for("lookup.species_detail", species_id=sp.id))

    return render_template(
        "lookup/species_form.html",
        form=form,
        sp=sp,
        edit=True,
        title=f"Edit Species — {sp.name_bg}"
    )


@bp.route("/species/<int:species_id>/delete", methods=["POST"])
@login_required
@admin_required
def species_delete(species_id):
    sp = db.get_or_404(Species, species_id)
    name = sp.name_bg
    log_action("species_deleted", "Species", sp.id, f"Deleted: {name}")
    db.session.delete(sp)
    db.session.commit()
    flash(f"Species '{name}' deleted.", "info")
    return redirect(url_for("lookup.species_list"))


# ── CSV IMPORT ────────────────────────────────────────────────────────────────

@bp.route("/species/import-csv", methods=["GET", "POST"])
@login_required
@admin_required
def species_import_csv():
    form = SpeciesCSVImportForm()

    if form.validate_on_submit():
        file_data = form.csv_file.data
        stream    = io.TextIOWrapper(file_data.stream, encoding="utf-8-sig")
        reader    = csv.DictReader(stream)

        imported  = 0
        skipped   = 0
        errors    = []

        BOOL_TRUE = {"true", "yes", "1", "da", "да"}

        for row_num, row in enumerate(reader, start=2):
            name_bg = (row.get("name_bg") or "").strip()
            if not name_bg:
                errors.append(f"Row {row_num}: missing name_bg — skipped.")
                skipped += 1
                continue

            if Species.query.filter(
                db.func.lower(Species.name_bg) == name_bg.lower()
            ).first():
                skipped += 1
                continue

            def _f(key):
                v = (row.get(key) or "").strip()
                try:
                    return float(v) if v else None
                except ValueError:
                    return None

            def _b(key):
                return (row.get(key) or "").strip().lower() in BOOL_TRUE

            sp = Species(
                name_bg         = name_bg,
                name_en         = (row.get("name_en") or "").strip() or None,
                scientific_name = (row.get("scientific_name") or "").strip() or None,
                min_size_cm     = _f("min_size_cm"),
                max_size_cm     = _f("max_size_cm"),
                season_start    = (row.get("season_start") or "").strip() or None,
                season_end      = (row.get("season_end") or "").strip() or None,
                daily_limit_kg  = _f("daily_limit_kg"),
                is_protected    = _b("is_protected"),
                notes           = (row.get("notes") or "").strip() or None,
            )
            db.session.add(sp)
            imported += 1

        db.session.commit()
        log_action("species_csv_import", "Species", None,
                   f"Imported {imported}, skipped {skipped}")

        msg = f"Import complete: {imported} species imported, {skipped} skipped (duplicates)."
        if errors:
            msg += f" {len(errors)} rows had errors (check logs)."
        flash(msg, "success" if not errors else "warning")
        return redirect(url_for("lookup.species_list"))

    return render_template(
        "lookup/species_import.html",
        form=form,
        title="Import Species from CSV"
    )


# ══════════════════════════════════════════════════════════════
#  GEAR TYPES
# ══════════════════════════════════════════════════════════════

@bp.route("/gear")
@login_required
@admin_required
def gear_list():
    q       = request.args.get("q", "").strip()
    legal_f = request.args.get("legal", "")
    page    = request.args.get("page", 1, type=int)

    query = GearType.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                GearType.code.ilike(like),
                GearType.name.ilike(like),
            )
        )
    if legal_f == "yes":
        query = query.filter_by(is_legal=True)
    elif legal_f == "no":
        query = query.filter_by(is_legal=False)

    pagination = query.order_by(GearType.code).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "lookup/gear_list.html",
        gears=pagination.items,
        pagination=pagination,
        q=q,
        legal_f=legal_f,
        total=GearType.query.count(),
        illegal_count=GearType.query.filter_by(is_legal=False).count(),
        title="Gear Type Catalogue"
    )


@bp.route("/gear/add", methods=["GET", "POST"])
@login_required
@admin_required
def gear_add():
    form = GearTypeForm()
    if form.validate_on_submit():
        if GearType.query.filter(
            db.func.upper(GearType.code) == form.code.data.strip().upper()
        ).first():
            flash("A gear type with this code already exists.", "danger")
        else:
            gt = GearType(
                code               = form.code.data.strip().upper(),
                name               = form.name.data.strip(),
                description        = form.description.data or None,
                mesh_size_required = form.mesh_size_required.data,
                min_mesh_size_mm   = form.min_mesh_size_mm.data,
                is_legal           = form.is_legal.data,
            )
            db.session.add(gt)
            db.session.commit()
            log_action("gear_type_created", "GearType", gt.id,
                       f"Code: {gt.code}, Legal: {gt.is_legal}")
            flash(f"Gear type '{gt.code} — {gt.name}' added.", "success")
            return redirect(url_for("lookup.gear_list"))

    return render_template(
        "lookup/gear_form.html",
        form=form,
        edit=False,
        title="Add Gear Type"
    )


@bp.route("/gear/<int:gear_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def gear_edit(gear_id):
    gt   = db.get_or_404(GearType, gear_id)
    form = GearTypeForm(obj=gt)

    if form.validate_on_submit():
        dup = GearType.query.filter(
            db.func.upper(GearType.code) == form.code.data.strip().upper(),
            GearType.id != gt.id
        ).first()
        if dup:
            flash("Another gear type already uses that code.", "danger")
        else:
            old_code           = gt.code
            gt.code               = form.code.data.strip().upper()
            gt.name               = form.name.data.strip()
            gt.description        = form.description.data or None
            gt.mesh_size_required = form.mesh_size_required.data
            gt.min_mesh_size_mm   = form.min_mesh_size_mm.data
            gt.is_legal           = form.is_legal.data
            gt.updated_at         = datetime.utcnow()
            db.session.commit()
            log_action("gear_type_edited", "GearType", gt.id,
                       f"Code: {old_code} → {gt.code}, Legal: {gt.is_legal}")
            flash(f"Gear type '{gt.code}' updated.", "success")
            return redirect(url_for("lookup.gear_list"))

    return render_template(
        "lookup/gear_form.html",
        form=form,
        gt=gt,
        edit=True,
        title=f"Edit Gear Type — {gt.code}"
    )


@bp.route("/gear/<int:gear_id>/delete", methods=["POST"])
@login_required
@admin_required
def gear_delete(gear_id):
    gt = db.get_or_404(GearType, gear_id)
    code = gt.code
    log_action("gear_type_deleted", "GearType", gt.id, f"Deleted: {code}")
    db.session.delete(gt)
    db.session.commit()
    flash(f"Gear type '{code}' deleted.", "info")
    return redirect(url_for("lookup.gear_list"))


# ══════════════════════════════════════════════════════════════
#  VIOLATION CATEGORIES
# ══════════════════════════════════════════════════════════════

@bp.route("/violations")
@login_required
@admin_required
def violation_codes_list():
    tab        = request.args.get("tab", "codes")
    categories = ViolationCategory.query.order_by(ViolationCategory.name).all()
    codes      = ViolationCode.query.order_by(ViolationCode.code).all()

    cat_form  = ViolationCategoryForm()
    code_form = ViolationCodeForm()
    code_form.set_category_choices()

    return render_template(
        "lookup/violation_codes.html",
        categories=categories,
        codes=codes,
        tab=tab,
        cat_form=cat_form,
        code_form=code_form,
        title="Violation Codes"
    )


# ── CATEGORIES ────────────────────────────────────────────────

@bp.route("/violations/categories/add", methods=["POST"])
@login_required
@admin_required
def violation_category_add():
    form = ViolationCategoryForm()
    if form.validate_on_submit():
        if ViolationCategory.query.filter(
            db.func.lower(ViolationCategory.name) == form.name.data.strip().lower()
        ).first():
            flash("Category already exists.", "danger")
        else:
            cat = ViolationCategory(name=form.name.data.strip())
            db.session.add(cat)
            db.session.commit()
            log_action("violation_category_created", "ViolationCategory", cat.id,
                       f"Name: {cat.name}")
            flash(f"Category '{cat.name}' added.", "success")
    else:
        for errs in form.errors.values():
            flash(", ".join(errs), "danger")
    return redirect(url_for("lookup.violation_codes_list", tab="categories"))


@bp.route("/violations/categories/<int:cat_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def violation_category_edit(cat_id):
    cat  = db.get_or_404(ViolationCategory, cat_id)
    form = ViolationCategoryForm(obj=cat)

    if form.validate_on_submit():
        dup = ViolationCategory.query.filter(
            db.func.lower(ViolationCategory.name) == form.name.data.strip().lower(),
            ViolationCategory.id != cat.id
        ).first()
        if dup:
            flash("Another category already uses that name.", "danger")
        else:
            old_name  = cat.name
            cat.name  = form.name.data.strip()
            db.session.commit()
            log_action("violation_category_edited", "ViolationCategory", cat.id,
                       f"{old_name} → {cat.name}")
            flash(f"Category renamed to '{cat.name}'.", "success")
            return redirect(url_for("lookup.violation_codes_list", tab="categories"))

    return render_template(
        "lookup/violation_category_edit.html",
        form=form,
        cat=cat,
        title=f"Edit Category — {cat.name}"
    )


@bp.route("/violations/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
@admin_required
def violation_category_delete(cat_id):
    cat = db.get_or_404(ViolationCategory, cat_id)
    if cat.codes:
        flash(
            f"Cannot delete '{cat.name}': it has {len(cat.codes)} violation code(s) assigned. "
            "Reassign or delete those codes first.",
            "danger"
        )
        return redirect(url_for("lookup.violation_codes_list", tab="categories"))
    name = cat.name
    log_action("violation_category_deleted", "ViolationCategory", cat.id,
               f"Deleted: {name}")
    db.session.delete(cat)
    db.session.commit()
    flash(f"Category '{name}' deleted.", "info")
    return redirect(url_for("lookup.violation_codes_list", tab="categories"))


# ── VIOLATION CODES ───────────────────────────────────────────

@bp.route("/violations/codes/add", methods=["POST"])
@login_required
@admin_required
def violation_code_add():
    form = ViolationCodeForm()
    form.set_category_choices()

    if form.validate_on_submit():
        if ViolationCode.query.filter(
            db.func.upper(ViolationCode.code) == form.code.data.strip().upper()
        ).first():
            flash(f"Code '{form.code.data}' already exists.", "danger")
        else:
            vc = ViolationCode(
                code             = form.code.data.strip().upper(),
                title            = form.title.data.strip(),
                description      = form.description.data or None,
                category_id      = form.category_id.data,
                default_severity = form.default_severity.data,
                law_article      = form.law_article.data.strip() or None,
                default_penalty  = form.default_penalty.data,
            )
            db.session.add(vc)
            db.session.commit()
            log_action("violation_code_created", "ViolationCode", vc.id,
                       f"Code: {vc.code}")
            flash(f"Violation code '{vc.code}' added.", "success")
    else:
        for errs in form.errors.values():
            flash(", ".join(errs), "danger")
    return redirect(url_for("lookup.violation_codes_list", tab="codes"))


@bp.route("/violations/codes/<int:code_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def violation_code_edit(code_id):
    vc   = db.get_or_404(ViolationCode, code_id)
    form = ViolationCodeForm(obj=vc)
    form.set_category_choices()

    if form.validate_on_submit():
        dup = ViolationCode.query.filter(
            db.func.upper(ViolationCode.code) == form.code.data.strip().upper(),
            ViolationCode.id != vc.id
        ).first()
        if dup:
            flash("Another violation code uses that code string.", "danger")
        else:
            old_code            = vc.code
            vc.code             = form.code.data.strip().upper()
            vc.title            = form.title.data.strip()
            vc.description      = form.description.data or None
            vc.category_id      = form.category_id.data
            vc.default_severity = form.default_severity.data
            vc.law_article      = form.law_article.data.strip() or None
            vc.default_penalty  = form.default_penalty.data
            db.session.commit()
            log_action("violation_code_edited", "ViolationCode", vc.id,
                       f"Code: {old_code} → {vc.code}")
            flash(f"Violation code '{vc.code}' updated.", "success")
            return redirect(url_for("lookup.violation_codes_list", tab="codes"))

    return render_template(
        "lookup/violation_code_edit.html",
        form=form,
        vc=vc,
        title=f"Edit Violation Code — {vc.code}"
    )


@bp.route("/violations/codes/<int:code_id>/delete", methods=["POST"])
@login_required
@admin_required
def violation_code_delete(code_id):
    vc = db.get_or_404(ViolationCode, code_id)
    if vc.violations:
        flash(
            f"Cannot delete code '{vc.code}': {len(vc.violations)} violation record(s) reference it.",
            "danger"
        )
        return redirect(url_for("lookup.violation_codes_list", tab="codes"))
    code = vc.code
    log_action("violation_code_deleted", "ViolationCode", vc.id, f"Deleted: {code}")
    db.session.delete(vc)
    db.session.commit()
    flash(f"Violation code '{code}' deleted.", "info")
    return redirect(url_for("lookup.violation_codes_list", tab="codes"))
