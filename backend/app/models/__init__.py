"""
app/models/__init__.py

INTENTIONALLY has NO eager imports.

WHY: Importing all models here causes payment.py (and other model files)
to run their class bodies a second time when any models submodule is
accessed during startup, because Python executes __init__.py on first
package access. This double-execution re-registers the same SQLAlchemy
mapped class against an already-registered Table name and raises:
  "Table 'X' is already defined for this MetaData instance."

HOW model registration works instead:
  create_tables() in app/db/base.py does explicit imports:
      import app.models.user
      import app.models.video
      import app.models.payment
  These run each module body exactly once, register all classes on
  Base.metadata, and then Base.metadata.create_all() can see every table.

HOW to import models in route files:
  from app.models.user    import User, UserSettings, SubscriptionTier
  from app.models.video   import Video, VideoScene, VideoStatus
  from app.models.payment import Payment, SubscriptionPlan, PaymentStatus
"""

# No imports here — see docstring above.
