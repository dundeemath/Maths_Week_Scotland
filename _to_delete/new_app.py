import math
import itertools
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, render, ui, reactive
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

appdir = Path(__file__).parent
IMG_PATH = appdir / "tsp_game_map.png"
img = mpimg.imread(str(IMG_PATH))
H, W = img.shape[0], img.shape[1]

CIRCLE_R = 26
CLICK_TOLERANCE = CIRCLE_R + 12

# The six trail stops used by this mini-game -- pixel coordinates on
# tsp_game_map.png (the coloured circles baked into that image). Stop 0
# (Fibonacci) is the fixed start, stop 5 (TSP) is the fixed end -- the
# player's job is to find the best order for the four stops in between.
STOPS = [
    (106.5, 803.9),   # 0. Fibonacci -- START (fixed)
    (152.5, 1035.2),  # 1. Phyllotaxis
    (163.0, 312.0),   # 2. Analemma
    (214.6, 626.9),   # 3. Konigsberg
    (311.5, 71.5),    # 4. Curvature
    (289.7, 306.0),   # 5. Travelling Salesman -- END (fixed)
]
STOP_SYMBOLS = ["φ", "σ", "√", "≤", "≥", "μ"]
STOP_NAMES = [
    "Fibonacci", "Phyllotaxis", "Analemma", "Königsberg", "Curvature",
    "Travelling Salesman",
]
START_IDX = 0
END_IDX = 5
MIDDLE_IDXS = [1, 2, 3, 4]
N_MIDDLE = len(MIDDLE_IDXS)


def open_route_length(order):
    """Length of an open path (no return leg), as a list of stop indices."""
    total = 0.0
    for i in range(len(order) - 1):
        ax_, ay_ = STOPS[order[i]]
        bx_, by_ = STOPS[order[i + 1]]
        total += math.hypot(ax_ - bx_, ay_ - by_)
    return total


def best_middle_order():
    """Exact optimum: only 4 stops to permute (24 routes), so always brute force."""
    best_order, best_len = None, math.inf
    for perm in itertools.permutations(MIDDLE_IDXS):
        order = [START_IDX] + list(perm) + [END_IDX]
        length = open_route_length(order)
        if length < best_len:
            best_len = length
            best_order = order
    return best_order, best_len


OPTIMAL_ORDER, OPTIMAL_LENGTH = best_middle_order()


def nearest_stop(cx, cy):
    best_i, best_d = None, CLICK_TOLERANCE
    for i, (x, y) in enumerate(STOPS):
        d = math.hypot(x - cx, y - cy)
        if d < best_d:
            best_i, best_d = i, d
    return best_i


stop_legend = ", ".join(
    f"{STOP_SYMBOLS[i]} {name}"
    + (" (start)" if i == START_IDX else " (end)" if i == END_IDX else "")
    for i, name in enumerate(STOP_NAMES)
)

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h5("Plan the middle leg"),
        ui.markdown(
            "Your route always starts at **φ Fibonacci** and ends at "
            "**μ Travelling Salesman**. Tap the four stops in between, "
            "in whatever order you think gives the shortest route."
        ),
        ui.markdown(f"_{stop_legend}_"),
        ui.input_action_button("clear_route", "Clear my route", width="100%"),
        ui.hr(),
        ui.input_radio_buttons(
            "show",
            "Show on the map",
            {"manual": "Your route", "optimal": "Optimal route"},
            selected="manual",
        ),
        ui.hr(),
        ui.output_text_verbatim("summary"),
        width=340,
    ),
    ui.output_plot("plot", click=True, width="100%", height="560px"),
)


def server(input: Inputs, output: Outputs, session: Session):
    manual_route = reactive.Value([])

    @reactive.Effect
    @reactive.event(input.clear_route)
    def _():
        manual_route.set([])

    @reactive.Effect
    @reactive.event(input.plot_click)
    def _():
        click = input.plot_click()
        if click is None:
            return
        idx = nearest_stop(click["x"], click["y"])
        if idx is None or idx in (START_IDX, END_IDX):
            return  # start/end are fixed -- only the four middle stops are clickable
        route = manual_route.get()
        if idx in route or len(route) >= N_MIDDLE:
            return  # each stop used once; use "Clear my route" to start over
        manual_route.set(route + [idx])

    @reactive.Calc
    def manual_info():
        route = manual_route.get()
        complete = len(route) == N_MIDDLE
        order = [START_IDX] + route + ([END_IDX] if complete else [])
        length = open_route_length(order) if complete else None
        return {"route": route, "complete": complete, "order": order, "length": length}

    @output
    @render.plot
    def plot():
        m_info = manual_info()
        fig, ax = plt.subplots(figsize=(W / 100, H / 100))
        ax.imshow(img, extent=[0, W, H, 0])
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)
        ax.axis("off")

        show = input.show()
        if show == "optimal":
            route_to_draw = OPTIMAL_ORDER
            colour = "#ffb703"
        else:
            route_to_draw = m_info["order"]
            colour = "#1d3557"

        if route_to_draw and len(route_to_draw) >= 2:
            xs = [STOPS[i][0] for i in route_to_draw]
            ys = [STOPS[i][1] for i in route_to_draw]
            ax.plot(xs, ys, "-", color=colour, linewidth=3, zorder=5, solid_capstyle="round")

        if show != "optimal":
            for order_pos, idx in enumerate(m_info["route"], start=1):
                x, y = STOPS[idx]
                ax.annotate(
                    str(order_pos), (x, y), xytext=(0, -40), textcoords="offset points",
                    color="#1d3557", ha="center", va="center", fontsize=13, fontweight="bold",
                    zorder=6,
                    bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="#1d3557", lw=1.5),
                )

        return fig

    @output
    @render.text
    def summary():
        m_info = manual_info()
        lines = [f"Middle stops placed: {len(m_info['route'])} of {N_MIDDLE}"]
        lines.append(f"Possible orderings: {math.factorial(N_MIDDLE)}")
        lines.append("")
        lines.append(f"Optimal route: {OPTIMAL_LENGTH:.0f} units")

        if m_info["complete"]:
            length = m_info["length"]
            lines.append(f"Your route: {length:.0f} units")
            pct = 100 * (length - OPTIMAL_LENGTH) / OPTIMAL_LENGTH if OPTIMAL_LENGTH > 0 else 0
            if pct > 0.5:
                lines.append(f"  {pct:.1f}% longer than optimal")
            else:
                lines.append("  you found the optimal route!")
        else:
            lines.append("Tap the four middle stops to complete your route.")

        return "\n".join(lines)


app = App(app_ui, server)
