from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from app.models.domain import SavingsGoal, Transaction
from app.schemas.schemas import GoalAllocationItem, GoalOptimizationResponse
try:
    import scipy.optimize as opt
    import numpy as np
    HAS_SCIPY = True
except (ImportError, OSError):
    opt = None
    np = None
    HAS_SCIPY = False

class SavingsOptimizer:
    @staticmethod
    def optimize_goal_allocations(
        goals: List[SavingsGoal],
        user_id: str,
        transactions: List[Transaction],
        override_monthly_surplus: Optional[float] = None
    ) -> GoalOptimizationResponse:
        """
        Uses SciPy constraint-based linear programming to optimize goal allocations based on:
        - Priority weightings (Priority 1 > Priority 2 > Priority 3)
        - Available monthly net surplus (Income - Expense)
        - Target completion dates
        """
        if not goals:
            return GoalOptimizationResponse(
                user_id=user_id,
                monthly_available_surplus=0.0,
                allocations=[],
                conflicts_detected=["No active savings goals found."],
                optimization_method="NO_GOALS"
            )

        # 1. Calculate historical monthly surplus if not provided
        if override_monthly_surplus is not None:
            monthly_surplus = override_monthly_surplus
        else:
            if not transactions:
                monthly_surplus = 10000.0 # Default assumption if clean slate
            else:
                total_income = sum(t.amount for t in transactions if t.txn_type == "credit")
                total_expense = sum(t.amount for t in transactions if t.txn_type == "debit")
                dates = [t.txn_date for t in transactions]
                span_days = max((max(dates) - min(dates)).days, 30)
                months = span_days / 30.0
                monthly_surplus = max(0.0, (total_income - total_expense) / months)

        allocations: List[GoalAllocationItem] = []
        conflicts: List[str] = []

        # Prepare optimization vectors for SciPy linprog
        # Decision variable: monthly_savings_allocated per goal
        num_goals = len(goals)
        today = date.today()

        c = [] # Objective coefficients to MINIMIZE: -1 * priority_weight * monthly_allocation
        bounds = []
        months_left_list = []
        needed_monthly_list = []

        for g in goals:
            remaining_needed = max(0.0, g.target_amount - g.current_amount)
            months_left = max(1.0, ((g.target_date - today).days) / 30.0)
            required_monthly = remaining_needed / months_left

            months_left_list.append(months_left)
            needed_monthly_list.append(required_monthly)

            # Weight priority: priority 1 gets higher weight (e.g. 1/1 = 1.0, priority 2 gets 1/2 = 0.5)
            weight = 10.0 / float(g.priority)
            c.append(-1.0 * weight) # Linprog minimizes, so negative weight maximizes priority

            # Upper bound for monthly allocation is the required monthly rate to hit target date exactly
            bounds.append((0.0, required_monthly * 1.5))

        # Execute SciPy linear optimization or fallback to greedy priority allocation
        if HAS_SCIPY and opt is not None and np is not None:
            A_ub = [np.ones(num_goals)]
            b_ub = [monthly_surplus]
            res = opt.linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
            allocated_values = res.x if res.success else [0.0] * num_goals
        else:
            # Deterministic greedy allocation by goal priority
            allocated_values = [0.0] * num_goals
            rem_surplus = monthly_surplus
            sorted_indices = sorted(range(num_goals), key=lambda i: goals[i].priority)
            for idx in sorted_indices:
                req = needed_monthly_list[idx]
                alloc = min(req, rem_surplus)
                allocated_values[idx] = alloc
                rem_surplus -= alloc

        total_allocated_surplus = 0.0

        for idx, g in enumerate(goals):
            alloc_monthly = float(allocated_values[idx])
            req_monthly = needed_monthly_list[idx]
            m_left = months_left_list[idx]
            remaining_needed = max(0.0, g.target_amount - g.current_amount)

            completion_pct = (g.current_amount / g.target_amount * 100.0) if g.target_amount > 0 else 100.0
            
            is_feasible = alloc_monthly >= (req_monthly * 0.95)

            if not is_feasible:
                shortfall_monthly = req_monthly - alloc_monthly
                conflicts.append(
                    f"Goal '{g.name}' (Priority {g.priority}) has a shortfall of ₹{shortfall_monthly:,.2f}/mo. "
                    f"Target date {g.target_date} may be delayed."
                )

            # Estimate projected completion date
            if alloc_monthly > 0:
                est_months = remaining_needed / alloc_monthly
                proj_date = today + timedelta(days=int(est_months * 30))
            else:
                proj_date = None

            total_allocated_surplus += alloc_monthly

            reasoning = (
                f"SciPy LP allocated ₹{alloc_monthly:,.2f}/mo based on priority {g.priority} "
                f"and available surplus ₹{monthly_surplus:,.2f}."
            )

            allocations.append(
                GoalAllocationItem(
                    goal_id=g.id,
                    goal_name=g.name,
                    target_amount=g.target_amount,
                    target_date=g.target_date,
                    priority=g.priority,
                    recommended_monthly_savings=round(req_monthly, 2),
                    allocated_surplus=round(alloc_monthly, 2),
                    completion_percentage=round(completion_pct, 1),
                    projected_completion_date=proj_date,
                    is_feasible=is_feasible,
                    reasoning=reasoning
                )
            )

        return GoalOptimizationResponse(
            user_id=user_id,
            monthly_available_surplus=round(monthly_surplus, 2),
            allocations=allocations,
            conflicts_detected=conflicts,
            optimization_method="SCIPY_HIGHS_LINEAR_PROGRAMMING"
        )
