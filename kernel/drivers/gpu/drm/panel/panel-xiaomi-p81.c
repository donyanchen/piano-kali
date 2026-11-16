// SPDX-License-Identifier: GPL-2.0-only
/*
 * Xiaomi Pad 8 Pro (piano) panel: p81 35-02-0b, dual DSI, DSC, video mode.
 *
 * There is no upstream driver for this panel. Everything here comes from the
 * factory device tree (piano-real.dtb), extracted with
 * scripts/extract-panel-seq.py into p81-35-02-0b.h:
 *
 *   - three refresh-rate modes (90/120/144 Hz), each with its own 894-byte
 *     init sequence (DSC PPS is inside it, command 0x91)
 *   - 1600x2136 per DSI link, two links -> 3200x2136
 *   - brightness is NOT a DSI command: it goes to two external ktz8866 chips
 *
 * v0 scope: power sequencing, init sequence, display on/off, backlight handle.
 * Still TODO: DSC host-side configuration, ESD recovery, panel-id matching for
 * the p81_42_02_0a variant (see the sibling data file).
 */

#include <linux/backlight.h>
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>

#include <drm/drm_mipi_dsi.h>
#include <drm/drm_modes.h>
#include <drm/drm_panel.h>

#include "p81-35-02-0b.h"

/* One 32-bit header per DSI message, as stored by the vendor DT:
 *   dtype(1) last(1) vc(1) ack(1) wait_ms(1) len(1) payload(len)
 * dtype 0x05/0x15 are short DCS writes, 0x39/0x29 long DCS writes.
 */
#define P81_HDR_LEN		6

struct p81_panel {
	struct drm_panel panel;
	struct mipi_dsi_device *dsi;
	struct gpio_desc *reset_gpio;
	struct regulator_bulk_data supplies[2];
	int num_supplies;
	struct backlight_device *backlight;
	bool prepared;
};

static const struct drm_display_mode p81_144_mode = {
	.clock = 549854,	/* (1600+21+16+16) * (2136+104+68+2) * 144 / 1000 */
	.hdisplay = 1600,
	.hsync_start = 1600 + 21,
	.hsync_end = 1600 + 21 + 16,
	.htotal = 1600 + 21 + 16 + 16,
	.vdisplay = 2136,
	.vsync_start = 2136 + 104,
	.vsync_end = 2136 + 104 + 68,
	.vtotal = 2136 + 104 + 68 + 2,
	.width_mm = 148,
	.height_mm = 198,
	.type = DRM_MODE_TYPE_DRIVER | DRM_MODE_TYPE_PREFERRED,
};

static inline struct p81_panel *to_p81(struct drm_panel *panel)
{
	return container_of(panel, struct p81_panel, panel);
}

/* Send one vendor blob (header + payload pairs) over DCS. */
static int p81_send_blob(struct mipi_dsi_device *dsi, const u8 *blob, size_t len)
{
	size_t i = 0;
	int ret;

	while (i + P81_HDR_LEN <= len) {
		u8 wait = blob[i + 4];
		u8 n = blob[i + 5];

		if (i + P81_HDR_LEN + n > len) {
			dev_err(&dsi->dev, "truncated command at %zu\n", i);
			return -EINVAL;
		}
		if (n) {
			ret = mipi_dsi_dcs_write_buffer(dsi, &blob[i + P81_HDR_LEN], n);
			if (ret < 0) {
				dev_err(&dsi->dev, "dcs write failed at %zu: %d\n", i, ret);
				return ret;
			}
		}
		if (wait)
			msleep(wait);
		i += P81_HDR_LEN + n;
	}
	return 0;
}

static int p81_prepare(struct drm_panel *panel)
{
	struct p81_panel *ctx = to_p81(panel);
	struct mipi_dsi_device *dsi = ctx->dsi;
	int ret;

	if (ctx->prepared)
		return 0;

	ret = regulator_bulk_enable(ctx->num_supplies, ctx->supplies);
	if (ret) {
		dev_err(&dsi->dev, "regulators failed: %d\n", ret);
		return ret;
	}

	/* vendor reset sequence: out of reset, hold, out again */
	if (ctx->reset_gpio) {
		gpiod_set_value_cansleep(ctx->reset_gpio, 1);
		usleep_range(10000, 12000);
		gpiod_set_value_cansleep(ctx->reset_gpio, 0);
		usleep_range(10000, 12000);
		gpiod_set_value_cansleep(ctx->reset_gpio, 1);
		usleep_range(10000, 12000);
	}

	ret = p81_send_blob(dsi, MDSS_DSI_P81_35_02_0B_144HZ_QCOM_MDSS_DSI_ON_COMMAND,
			    sizeof(MDSS_DSI_P81_35_02_0B_144HZ_QCOM_MDSS_DSI_ON_COMMAND));
	if (ret) {
		dev_err(&dsi->dev, "init sequence failed: %d\n", ret);
		goto err_regs;
	}

	/* the blob already ends with 0x11 + 0x29, but be explicit */
	ret = mipi_dsi_dcs_exit_sleep_mode(dsi);
	if (ret < 0)
		goto err_regs;
	msleep(120);
	ret = mipi_dsi_dcs_set_display_on(dsi);
	if (ret < 0)
		goto err_regs;
	msleep(20);

	ctx->prepared = true;
	return 0;

err_regs:
	regulator_bulk_disable(ctx->num_supplies, ctx->supplies);
	return ret;
}

static int p81_enable(struct drm_panel *panel)
{
	struct p81_panel *ctx = to_p81(panel);

	if (ctx->backlight) {
		backlight_enable(ctx->backlight);
		return 0;
	}
	return 0;
}

static int p81_disable(struct drm_panel *panel)
{
	struct p81_panel *ctx = to_p81(panel);

	if (ctx->backlight)
		backlight_disable(ctx->backlight);
	return 0;
}

static int p81_unprepare(struct drm_panel *panel)
{
	struct p81_panel *ctx = to_p81(panel);
	struct mipi_dsi_device *dsi = ctx->dsi;

	if (!ctx->prepared)
		return 0;

	/* display off + sleep in, as in the vendor off-command */
	mipi_dsi_dcs_set_display_off(dsi);
	msleep(20);
	mipi_dsi_dcs_enter_sleep_mode(dsi);
	msleep(100);

	if (ctx->reset_gpio)
		gpiod_set_value_cansleep(ctx->reset_gpio, 0);
	regulator_bulk_disable(ctx->num_supplies, ctx->supplies);

	ctx->prepared = false;
	return 0;
}

static int p81_get_modes(struct drm_panel *panel, struct drm_connector *connector)
{
	struct drm_display_mode *mode;

	mode = drm_mode_duplicate(connector->dev, &p81_144_mode);
	if (!mode)
		return -ENOMEM;
	drm_mode_set_name(mode);
	mode->type |= DRM_MODE_TYPE_PREFERRED;
	drm_mode_probed_add(connector, mode);
	connector->display_info.width_mm = p81_144_mode.width_mm;
	connector->display_info.height_mm = p81_144_mode.height_mm;
	return 1;
}

static const struct drm_panel_funcs p81_funcs = {
	.prepare = p81_prepare,
	.enable = p81_enable,
	.disable = p81_disable,
	.unprepare = p81_unprepare,
	.get_modes = p81_get_modes,
};

static int p81_probe(struct mipi_dsi_device *dsi)
{
	struct device *dev = &dsi->dev;
	struct p81_panel *ctx;
	int ret;

	/* v6.15 dropped drm_panel_init(); the panel is now allocated through
	 * devm_drm_panel_alloc(), which also sets up the refcounted base. */
	ctx = devm_drm_panel_alloc(dev, struct p81_panel, panel,
				   &p81_funcs, DRM_MODE_CONNECTOR_DSI);
	if (IS_ERR(ctx))
		return PTR_ERR(ctx);

	ctx->supplies[0].supply = "vddi";
	ctx->supplies[1].supply = "avdd";
	/* The board DT may not describe the panel rails (the vendor DT keeps them
	 * implicit, powered by the bootloader). Treat a missing supply as "none"
	 * instead of failing probe. */
	ret = devm_regulator_bulk_get(dev, ARRAY_SIZE(ctx->supplies), ctx->supplies);
	if (ret == -ENODEV) {
		dev_info(dev, "no panel supplies described, continuing\n");
		ctx->num_supplies = 0;
	} else if (ret) {
		return dev_err_probe(dev, ret, "regulators\n");
	} else {
		ctx->num_supplies = ARRAY_SIZE(ctx->supplies);
	}

	ctx->reset_gpio = devm_gpiod_get_optional(dev, "reset", GPIOD_OUT_LOW);
	if (IS_ERR(ctx->reset_gpio))
		return dev_err_probe(dev, PTR_ERR(ctx->reset_gpio), "reset gpio\n");

	ctx->dsi = dsi;
	mipi_dsi_set_drvdata(dsi, ctx);

	dsi->lanes = 4;
	dsi->format = MIPI_DSI_FMT_RGB888;
	dsi->mode_flags = MIPI_DSI_MODE_VIDEO | MIPI_DSI_MODE_VIDEO_BURST |
			  MIPI_DSI_MODE_NO_EOT_PACKET;

	/* The DSI host must be in LP-11 before the panel is powered up. */
	ctx->panel.prepare_prev_first = true;

	ret = drm_panel_of_backlight(&ctx->panel);
	if (ret)
		return dev_err_probe(dev, ret, "backlight\n");
	ctx->backlight = ctx->panel.backlight;

	drm_panel_add(&ctx->panel);

	ret = mipi_dsi_attach(dsi);
	if (ret) {
		drm_panel_remove(&ctx->panel);
		return dev_err_probe(dev, ret, "dsi attach\n");
	}

	return 0;
}

static void p81_remove(struct mipi_dsi_device *dsi)
{
	struct p81_panel *ctx = mipi_dsi_get_drvdata(dsi);

	mipi_dsi_detach(dsi);
	drm_panel_remove(&ctx->panel);
}

static const struct of_device_id p81_of_match[] = {
	{ .compatible = "xiaomi,p81-35-02-0b" },
	{ }
};
MODULE_DEVICE_TABLE(of, p81_of_match);

static struct mipi_dsi_driver p81_driver = {
	.probe = p81_probe,
	.remove = p81_remove,
	.driver = {
		.name = "panel-xiaomi-p81",
		.of_match_table = p81_of_match,
	},
};
module_mipi_dsi_driver(p81_driver);

MODULE_AUTHOR("piano-kali");
MODULE_DESCRIPTION("Xiaomi Pad 8 Pro p81 35-02-0b DSI panel");
MODULE_LICENSE("GPL");