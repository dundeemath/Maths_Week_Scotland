import math
import itertools
from pathlib import Path

from shiny import App, Inputs, Outputs, Session, render, ui, reactive
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

appdir = Path(__file__).parent
IMG_PATH = appdir / "botanicmap.png"
img = mpimg.imread(str(IMG_PATH))
H, W = img.shape[0], img.shape[1]

BRUTE_FORCE_LIMIT = 9
CLICK_TOLERANCE = 0.035 * W

# Fixed exhibition stops -- pixel coordinates on botanicmap.png.
# Stop 1 is STOPS[0] / STOP_NAMES[0], matching how the stops are numbered around the physical trail, and so on.
STOPS = [
    (96, 108),   # 1. The Glass House Cactus Garden
    (219, 77),   # 2. The Chalet
    (272, 69),   # 3. The Good Grief Garden
    (224, 133),  # 4. The Patterson Education Centre
    (298, 174),  # 5. The Eddie Kemp Pavilion
]
STOP_NAMES = [
    "The Glass House Cactus Garden",
    "The Chalet",
    "The Good Grief Garden",
    "The Patterson Education Centre",
    "The Eddie Kemp Pavilion",
]
N_STOPS = len(STOPS)

TRAIL_ORDER = list(range(N_STOPS))  # the fixed order stops are numbered in, walking the physical trail


def route_length(order, stops):
    total = 0.0
    n = len(order)
    for i in range(n):
        ax_, ay_ = stops[order[i]]
        bx_, by_ = stops[order[(i + 1) % n]]
        total += math.hypot(ax_ - bx_, ay_ - by_)
    return total


def nearest_neighbour(indices, stops):
    remaining = set(indices[1:])
    order = [indices[0]]
    while remaining:
        last = order[-1]
        lx, ly = stops[last]
        nxt = min(remaining, key=lambda j: math.hypot(lx - stops[j][0], ly - stops[j][1]))
        order.append(nxt)
        remaining.remove(nxt)
    return order


def two_opt(order, stops):
    order = order[:]
    n = len(order)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                a, b = order[i], order[i + 1]
                c, d = order[j], order[(j + 1) % n]
                old = math.hypot(stops[a][0] - stops[b][0], stops[a][1] - stops[b][1]) + math.hypot(
                    stops[c][0] - stops[d][0], stops[c][1] - stops[d][1]
                )
                new = math.hypot(stops[a][0] - stops[c][0], stops[a][1] - stops[c][1]) + math.hypot(
                    stops[b][0] - stops[d][0], stops[b][1] - stops[d][1]
                )
                if new < old - 1e-9:
                    order[i + 1 : j + 1] = reversed(order[i + 1 : j + 1])
                    improved = True
    return order


def brute_force(indices, stops):
    best_order = None
    best_len = math.inf
    first = indices[0]
    rest = indices[1:]
    for perm in itertools.permutations(rest):
        order = [first] + list(perm)
        length = route_length(order, stops)
        if length < best_len:
            best_len = length
            best_order = order
    return best_order, best_len


def nearest_stop(cx, cy):
    best_i, best_d = None, CLICK_TOLERANCE
    for i, (x, y) in enumerate(STOPS):
        d = math.hypot(x - cx, y - cy)
        if d < best_d:
            best_i, best_d = i, d
    return best_i


stop_legend = ", ".join(f"{i + 1} = {name}" for i, name in enumerate(STOP_NAMES))

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h5("Simulate a route"),
        ui.markdown(f"_{stop_legend}_"),
        ui.input_radio_buttons(
            "click_mode",
            "Clicking the map:",
            {"select": "Selects / deselects stops", "route": "Adds the next stop to your route"},
            selected="select",
        ),
        ui.row(
            ui.column(6, ui.input_action_button("clear_selection", "Clear stops", width="100%")),
            ui.column(6, ui.input_action_button("clear_route", "Clear my route", width="100%")),
        ),
        ui.hr(),
        ui.input_radio_buttons(
            "method",
            "Algorithm route",
            {"nn": "Nearest neighbour", "nn2opt": "Nearest neighbour + 2-opt"},
            selected="nn2opt",
        ),
        ui.input_checkbox(
            "exact",
            "Also find the exact best route (feasible up to about 9 stops)",
            value=False,
        ),
        ui.hr(),
        ui.input_radio_buttons(
            "show",
            "Show on the map",
            {
                "trail": "The route you walked today",
                "manual": "Your simulated route",
                "algo": "Algorithm route",
                "exact": "Optimal route",
            },
            selected="trail",
        ),
        ui.hr(),
        ui.output_text_verbatim("summary"),
        ui.hr(),
        ui.h5("The route you walked today"),
        ui.output_ui("trail_status"),
        width=360,
    ),
    ui.navset_tab(
        ui.nav_panel("Plan a route", ui.output_plot("plot", click=True)),
        ui.nav_panel("Trail map", ui.output_image("trail_map_legend")),
    ),
)


def server(input: Inputs, output: Outputs, session: Session):
    selected = reactive.Value(set())
    manual_route = reactive.Value([])

    @reactive.Effect
    @reactive.event(input.clear_selection)
    def _():
        selected.set(set())
        manual_route.set([])

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
        if idx is None:
            return

        if input.click_mode() == "select":
            sel = set(selected.get())
            if idx in sel:
                sel.discard(idx)
            else:
                sel.add(idx)
            selected.set(sel)
            manual_route.set([])  # selection changed -> your route no longer applies
        else:
            sel = selected.get()
            if idx not in sel:
                return  # can only route through selected stops
            route = manual_route.get()
            if idx in route:
                return  # each stop used once; use "Clear my route" to start over
            manual_route.set(route + [idx])

    @reactive.Calc
    def algo_info():
        indices = sorted(selected.get())
        n = len(indices)
        if n < 3:
            return {"n": n, "order": None, "length": None, "possible": None, "exact": None}

        if input.method() == "nn":
            order = nearest_neighbour(indices, STOPS)
        else:
            order = two_opt(nearest_neighbour(indices, STOPS), STOPS)
        length = route_length(order, STOPS)
        possible = math.factorial(n - 1) // 2  # distinct tours, fixed start, direction symmetry removed

        exact = None
        if input.exact() and 3 <= n <= BRUTE_FORCE_LIMIT:
            best_order, best_len = brute_force(indices, STOPS)
            exact = {"order": best_order, "length": best_len}

        return {"n": n, "order": order, "length": length, "possible": possible, "exact": exact}

    @reactive.Calc
    def manual_info():
        sel = selected.get()
        route = manual_route.get()
        complete = len(sel) >= 3 and set(route) == sel
        length = route_length(route, STOPS) if complete else None
        return {"route": route, "complete": complete, "length": length}

    @reactive.Calc
    def trail_comparison():
        # The fixed order the stops are numbered in around the physical
        # trail, compared against a fast algorithm route and the true
        # optimum -- both computed over the same full set of stops.
        indices = list(range(N_STOPS))
        algo_order = two_opt(nearest_neighbour(indices, STOPS), STOPS)
        algo_length = route_length(algo_order, STOPS)
        trail_length = route_length(TRAIL_ORDER, STOPS)
        exact = None
        if N_STOPS <= BRUTE_FORCE_LIMIT:
            best_order, best_len = brute_force(indices, STOPS)
            exact = {"order": best_order, "length": best_len}
        return {
            "trail_length": trail_length,
            "algo_order": algo_order,
            "algo_length": algo_length,
            "exact": exact,
        }

    @output
    @render.plot
    def plot():
        info = algo_info()
        m_info = manual_info()
        fig, ax = plt.subplots(figsize=(7, 7 * H / W))
        ax.imshow(img, extent=[0, W, H, 0])
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)
        ax.axis("off")

        show = input.show()
        route_to_draw = None
        closed = True
        if show == "manual":
            route_to_draw = m_info["route"]
            closed = m_info["complete"]
        elif show == "algo":
            route_to_draw = info["order"]
        elif show == "exact":
            route_to_draw = info["exact"]["order"] if info["exact"] else None
        elif show == "trail":
            route_to_draw = TRAIL_ORDER
            closed = True

        if route_to_draw and len(route_to_draw) >= 2:
            xs = [STOPS[i][0] for i in route_to_draw]
            ys = [STOPS[i][1] for i in route_to_draw]
            if closed:
                xs.append(STOPS[route_to_draw[0]][0])
                ys.append(STOPS[route_to_draw[0]][1])
            colour = "#f4a261" if show == "trail" else "#e63946"
            ax.plot(xs, ys, "-", color=colour, linewidth=2.5, zorder=2)

        sel = selected.get()
        for i, (x, y) in enumerate(STOPS):
            is_selected = i in sel
            colour = "#2a9d8f" if is_selected else "#adb5bd"
            ax.scatter(
                [x], [y], s=170, color=colour, edgecolor="white", linewidth=1.5,
                zorder=3, alpha=1.0 if is_selected else 0.6,
            )
            ax.annotate(
                str(i + 1), (x, y), color="white", ha="center", va="center",
                fontsize=9, fontweight="bold", zorder=4,
            )

        return fig

    @output
    @render.text
    def summary():
        info = algo_info()
        m_info = manual_info()
        n = info["n"]
        lines = [f"Stops selected: {n} of {N_STOPS}"]

        if n < 3:
            lines.append("Select at least 3 stops to build a route.")
            return "\n".join(lines)

        lines.append(f"Possible distinct routes: {info['possible']:,}")
        lines.append("")

        method_name = "nearest neighbour" if input.method() == "nn" else "nearest neighbour + 2-opt"
        lines.append(f"Algorithm ({method_name}): {info['length']:.0f} units")

        if m_info["complete"]:
            lines.append(f"Your simulated route: {m_info['length']:.0f} units")
        else:
            lines.append(f"Your simulated route: {len(m_info['route'])} of {n} stops placed")

        if input.exact():
            if info["exact"] is not None:
                exact_len = info["exact"]["length"]
                lines.append(f"Optimal route: {exact_len:.0f} units")

                algo_pct = 100 * (info["length"] - exact_len) / exact_len if exact_len > 0 else 0
                if algo_pct > 0.05:
                    lines.append(f"  algorithm is {algo_pct:.1f}% longer than optimal")
                else:
                    lines.append("  algorithm found the optimal route!")

                if m_info["complete"]:
                    manual_pct = 100 * (m_info["length"] - exact_len) / exact_len if exact_len > 0 else 0
                    if manual_pct > 0.05:
                        lines.append(f"  your route is {manual_pct:.1f}% longer than optimal")
                    else:
                        lines.append("  your route found the optimal route!")
            else:
                lines.append(
                    f"With {n} stops there are {math.factorial(n):,} possible orderings to check "
                    "one-by-one -- far too many to try them all."
                )

        return "\n".join(lines)

    @output
    @render.ui
    def trail_status():
        info = trail_comparison()
        names = ", ".join(f"{i + 1}. {STOP_NAMES[i]}" for i in TRAIL_ORDER)
        lines = [f"**The order you walked today:** {names}"]
        lines.append(f"\nDistance walked: {info['trail_length']:.0f} units")
        lines.append(f"\nFast algorithm's route: {info['algo_length']:.0f} units")

        if info["exact"] is not None:
            exact_len = info["exact"]["length"]
            lines.append(f"\nShortest possible route: {exact_len:.0f} units")
            pct = 100 * (info["trail_length"] - exact_len) / exact_len if exact_len > 0 else 0
            if pct > 0.05:
                lines.append(f"\nYou walked {pct:.1f}% further today than the shortest possible route.")
            else:
                lines.append("\nYou walked the shortest possible route today!")

        return ui.markdown("\n".join(lines))


    @output
    @render.image
    def trail_map_legend():
        return {"src": str(appdir / "modified_schematic.png"), "width": "100%"}


app = App(app_ui, server)
