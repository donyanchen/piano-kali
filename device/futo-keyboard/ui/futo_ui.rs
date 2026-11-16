// SPDX-License-Identifier: MIT
// Native Linux rendering of FUTO's ActionBar / v2keyboard interaction model.
// Upstream reference: android-keyboard@7d61ab4, ActionBar.kt, Keyboard.kt,
// Special/symbols*.yaml and DefaultLightDark.kt. Upstream notices/terms remain
// in the prepared source and installed FUTO package; this is not an official UI.
use iced::{Color, Element, Length, Theme, alignment::{Horizontal, Vertical},
    widget::{Column, Container, Row, Scrollable, Space, Svg, Text, button::{Status, Style}, text::Shaping}};
use crate::{app::Message, config::Placement, layout::{KLength, ToElementCommonParams},
    state::{CloseOpSource, ImEvent, KeyboardEvent, LayoutEvent, WindowEvent, WindowManagerEvent},
    widget::{ExtButton, Movable, Toggle, ToggleCondition}, window::WindowManagerMode};
use std::time::Duration;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Page { #[default] Keyboard, Symbols, SymbolsShift, Emoji, Edit, Settings, Candidates, About }
#[derive(serde::Deserialize)]
pub struct EmojiCategory { label: String, icon: String, items: Vec<String> }
#[derive(serde::Deserialize)]
struct EmojiData { categories: Vec<EmojiCategory> }
pub struct UiState { pub page: Page, pub actions: bool, pub emoji_category: usize, categories: Vec<EmojiCategory> }
impl Default for UiState {
    fn default() -> Self {
        let categories = std::fs::read_to_string("/usr/share/sheng-futo-keyboard/emoji.toml").ok()
            .filter(|data| data.len() < 262144).and_then(|data| toml::from_str::<EmojiData>(&data).ok()).map(|data| data.categories).unwrap_or_default();
        Self { page: Page::Keyboard, actions: false, emoji_category: 0, categories }
    }
}

fn rgb(hex: u32) -> Color { Color::from_rgb8((hex >> 16) as u8, (hex >> 8) as u8, hex as u8) }
pub fn key_style(theme: &Theme, pressed: bool, functional: bool, enter: bool) -> Style {
    let dark = theme.extended_palette().is_dark;
    let (normal, function, press, primary, on_primary) = if dark {
        (0x1e2024, 0x17181c, 0x3c3f47, 0xb2c8ff, 0x131d36)
    } else { (0xffffff, 0xf7f7f7, 0xd4d5d9, 0x0a1633, 0xf2f6ff) };
    Style { background: Some(rgb(if pressed { press } else if enter { primary } else if functional { function } else { normal }).into()),
        text_color: if enter { rgb(on_primary) } else { theme.palette().text },
        border: iced::border::rounded(if enter { 128 } else { 9 }), ..Default::default() }
}
pub fn icon<'a>(name: &str, size: f32, enter: bool) -> Element<'a, Message> {
    let path = std::path::PathBuf::from("/usr/share/sheng-futo-keyboard/icons").join(format!("{name}.svg"));
    Svg::new(iced::advanced::svg::Handle::from_path(path)).width(size).height(size)
        .style(move |theme: &Theme, _| iced::widget::svg::Style { color: Some(if enter { key_style(theme, false, true, true).text_color } else { theme.palette().text }) }).into()
}
fn button<'a>(label: impl Into<String>, action: Message, width: impl Into<Length>, height: f32, primary: bool) -> Element<'a, Message> {
    let label = label.into();
    let glyph = match label.as_str() { "›" => Some("chevron_right"), "‹" => Some("chevron_down"), "⌃" => Some("chevron_up"), "⌄" => Some("chevron_down"), "⇧" => Some("shift"), "⇪" => Some("shiftshifted"), "☺" => Some("smile"), "⚙" => Some("settings"), "↔" => Some("edit_text"), "globe" => Some("globe"), "mic" => Some("mic"), "clipboard" => Some("clipboard"), "undo" => Some("undo"), "redo" => Some("redo"), "keyboard" => Some("keyboard_icon"), _ => None };
    let keycap = matches!(label.as_str(), "?123" | "ABC" | "=\\<" | "⇧" | "⇪" | "☺");
    let content: Element<'a, Message> = if let Some(name) = glyph { icon(name, (height * if keycap { 0.5 } else { 0.55 }).clamp(20.0, 44.0), primary) }
        else { Text::new(label).font(iced::Font::with_name("Roboto")).size((height * if keycap { 0.29 } else { 0.38 }).clamp(14.0, 26.0)).shaping(Shaping::Advanced).into() };
    ExtButton::new(Container::new(content).center(Length::Fill))
        .width(width).height(height).padding(0)
        .on_release_with(Some(move || action.clone()))
        .style(move |theme, state| {
            let mut style = key_style(theme, matches!(state, Status::Pressed), true, primary);
            if !primary && !keycap && !matches!(state, Status::Pressed) { style.background = None; }
            style.border = iced::border::rounded(if primary { 128 } else { 9 });
            style
        }).into()
}
fn page_button<'a>(text: &str, page: Page, width: impl Into<Length>, height: f32) -> Element<'a, Message> {
    button(text, LayoutEvent::FutoPage(page).into(), width, height, false)
}
fn stroke(sym: u32, ctrl: bool, shift: bool) -> Message { KeyboardEvent::FutoStroke(sym, ctrl, shift).into() }
fn key<'a>(params: &ToElementCommonParams<'a>, name: &str, width: f32, height: f32, unit: KLength) -> Element<'a, Message> {
    let chinese = params.state.im().im_name().map(|name| name.as_str()) == Some("msime");
    params.state.keyboard().key_with_case(name.to_string().into(), unit, (width.into(), height.into()), Some(chinese))
}
fn symbol_key<'a>(params: &ToElementCommonParams<'a>, c: char, width: f32, height: f32, unit: KLength) -> Element<'a, Message> {
    if !c.is_ascii() { return button(c.to_string(), KeyboardEvent::FutoCommit(c.to_string()).into(), width, height, false); }
    key(params, &format!("k_u{:x}", c as u32), width, height, unit)
}
fn language(params: &ToElementCommonParams<'_>) -> Message {
    let chinese = params.state.im().im_name().map(|s| s.as_str()) == Some("msime");
    ImEvent::SelectIm(if chinese { "sheng-futo" } else { "msime" }.to_string()).into()
}
fn hide(params: &ToElementCommonParams<'_>) -> Message {
    if params.state.window_manager_mode() == WindowManagerMode::KwinLockScreen {
        crate::dbus::server::ImPanelEvent::NewVisibleRequest(false).into()
    } else { WindowManagerEvent::CloseKeyboard(CloseOpSource::UserAction).into() }
}

pub fn view<'a>(ui: &UiState, params: &ToElementCommonParams<'a>, unit: KLength,
    width: f32, height: f32, raw_settings: Option<Element<'a, Message>>) -> Element<'a, Message> {
    let normal = params.state.window_manager_mode() == WindowManagerMode::Normal;
    let page = if !normal && !matches!(ui.page, Page::Keyboard | Page::Symbols | Page::SymbolsShift) { Page::Keyboard } else { ui.page };
    let scale = (width / 393.0).clamp(0.8, 1.65);
    let edge = 3.0 * scale;
    let toolbar_h = 40.0 * scale;
    let grip_h = 28.0 * scale;
    let body_h = height - toolbar_h - grip_h - edge * 4.0 - if ui.actions { toolbar_h } else { 0.0 };
    let inner_w = width - edge * 2.0;
    let mut grip: Element<'a, Message> = Space::new().height(grip_h).into();
    if normal && params.state.placement() == Placement::Float {
        let id = params.window_id;
        let movable = params.state.movable(id);
        let handle = Container::new(Container::new(Space::new().width(76.0 * scale).height(3.0 * scale))
            .style(|theme: &Theme| iced::widget::container::Style {
                background: Some(theme.palette().text.scale_alpha(0.25).into()), border: iced::border::rounded(2), ..Default::default() }))
            .width(Length::Fill).height(grip_h).align_x(Horizontal::Center).align_y(Vertical::Center);
        let state = params.state;
        grip = Toggle::new(Movable::new(handle, move |delta| state.new_position_message(id, delta).unwrap_or(Message::Nothing), movable)
            .on_move_end(WindowEvent::SetMovable(id, false).into()), ToggleCondition::LongPress(Duration::from_millis(700)))
            .on_toggle(WindowEvent::SetMovable(id, !movable).into()).into();
    }
    let mut bar = Row::new().height(toolbar_h).align_y(Vertical::Center).spacing(0);
    let expand = ExtButton::new(Container::new(icon(if ui.actions { "chevron_down" } else { "chevron_right" }, 20.0 * scale, false))
        .center(32.0 * scale).style(|theme: &Theme| iced::widget::container::Style {
            background: key_style(theme, false, false, false).background, border: iced::border::rounded(128), ..Default::default() }))
        .width(42.0 * scale).height(toolbar_h).padding([4.0 * scale, 5.0 * scale])
        .on_release_with(Some(|| LayoutEvent::FutoActions.into())).style(|_, _| Style::default());
    bar = bar.push(expand);
    let candidates = params.state.im().candidate_area_state();
    if page != Page::Keyboard || raw_settings.is_some() {
        bar = bar.push(page_button("⌨  返回键盘", Page::Keyboard, Length::Fill, toolbar_h));
    } else if candidates.has_candidate() {
        let cursor = candidates.cursor();
        for (i, candidate) in candidates.candidate_list().iter().take(3).enumerate() {
            let label = candidate.iter().map(|(s, _)| s.as_str()).collect::<String>();
            if i > 0 { bar = bar.push(Container::new(Space::new().width(1).height(20.0 * scale)).style(|theme: &Theme| iced::widget::container::Style { background: Some(theme.palette().text.scale_alpha(0.3).into()), ..Default::default() })); }
            bar = bar.push(button(label, ImEvent::SelectCandidate(cursor + i).into(), Length::FillPortion(1), toolbar_h, false));
        }
        bar = bar.push(page_button("⌃", Page::Candidates, 30.0 * scale, toolbar_h));
    } else {
        bar = bar.push(Space::new().width(Length::Fill));
    }
    if normal { bar = bar.push(button("mic", crate::app::KeyboardNotification::Info("离线语音尚未移植；此版本不会录音。".to_string()).into(), 42.0 * scale, toolbar_h, false)); }
    let body = if let Some(settings) = raw_settings { settings }
        else { panel(ui, page, params, unit, inner_w, body_h, normal) };
    let footer = Row::new().height(grip_h).align_y(Vertical::Center)
        .push(button("⌄", hide(params), 42.0 * scale, grip_h, false)).push(grip)
        .push(button("keyboard", language(params), 42.0 * scale, grip_h, false));
    let mut content = Column::new().width(width).height(height).padding(edge).spacing(edge);
    if ui.actions {
        let mut actions = Row::new().height(toolbar_h).align_y(Vertical::Center);
        for (label, action) in [("globe", language(params)), ("undo", stroke('z' as u32, true, false)), ("redo", stroke('z' as u32, true, true)),
            ("↔", LayoutEvent::FutoPage(Page::Edit).into()), ("clipboard", stroke('v' as u32, true, false)), ("⚙", LayoutEvent::FutoPage(Page::Settings).into())] {
            actions = actions.push(button(label, action, Length::FillPortion(1), toolbar_h, false));
        }
        content = content.push(actions);
    }
    Container::new(content.push(bar).push(Container::new(body).width(inner_w).height(body_h)).push(footer))
        .style(move |theme: &Theme| iced::widget::container::Style {
            background: Some(theme.palette().background.into()), text_color: Some(theme.palette().text),
            border: iced::border::rounded(if normal { 20 } else { 0 }), ..Default::default() }).into()
}

fn panel<'a>(ui: &UiState, page: Page, params: &ToElementCommonParams<'a>, unit: KLength, width: f32, height: f32, normal: bool) -> Element<'a, Message> {
    let gap = width * 0.009;
    let h = (height - gap * 3.0) / 4.0;
    let w = (width - gap * 9.0) / 10.0;
    let mut column = Column::new().spacing(gap).height(height).width(width);
    match page {
        Page::Keyboard => {
            for (letters, offset) in [("qwertyuiop", 0.0), ("asdfghjkl", (w + gap) * 0.5)] {
                let mut row = Row::new().spacing(gap).height(h);
                if offset > 0.0 { row = row.push(Space::new().width(offset)); }
                for c in letters.chars() { row = row.push(key(params, &format!("k_{c}"), w, h, unit)); }
                column = column.push(row);
            }
            let shift = params.state.keyboard().futo_shift();
            let fw = (width - 7.0 * w - 8.0 * gap) / 2.0;
            let mut row = Row::new().spacing(gap).height(h)
                .push(button(if shift == 2 { "⇪" } else { "⇧" }, KeyboardEvent::FutoShift.into(), fw, h, shift > 0));
            for c in "zxcvbnm".chars() { row = row.push(key(params, &format!("k_{c}"), w, h, unit)); }
            row = row.push(key(params, "k_backspace", fw, h, unit));
            column = column.push(row);
        }
        Page::Symbols | Page::SymbolsShift => {
            let (first, second, third) = if page == Page::Symbols {
                ("1234567890", "@#$_%&-+()", "*\"':;!?")
            } else { ("~`|•√π÷×¶∆", "£€¥¢^°={}\\", "©®™℅[]<") };
            for symbols in [first, second] {
                let mut row = Row::new().spacing(gap).height(h);
                for c in symbols.chars() { row = row.push(symbol_key(params, c, w, h, unit)); }
                column = column.push(row);
            }
            let fw = (width - 7.0 * w - 8.0 * gap) / 2.0;
            let mut row = Row::new().spacing(gap).height(h).push(page_button(if page == Page::Symbols { "=\\<" } else { "?123" },
                if page == Page::Symbols { Page::SymbolsShift } else { Page::Symbols }, fw, h));
            for c in third.chars() { row = row.push(symbol_key(params, c, w, h, unit)); }
            column = column.push(row.push(key(params, "k_backspace", fw, h, unit)));
        }
        Page::Emoji => {
            let mut emojis = Column::new().spacing(gap);
            let mut tabs = Row::new().spacing(gap);
            for (index, category) in ui.categories.iter().enumerate() {
                tabs = tabs.push(button(format!("{} {}", category.icon, category.label), LayoutEvent::FutoEmojiCategory(index).into(), Length::FillPortion(1), h * 0.65, index == ui.emoji_category));
            }
            let category = ui.categories.get(ui.emoji_category).or_else(|| ui.categories.first());
            for items in category.map(|c| c.items.as_slice()).unwrap_or(&[]).chunks(8) {
                let mut row = Row::new().spacing(gap);
                for value in items { row = row.push(button(value.clone(), KeyboardEvent::FutoCommit(value.clone()).into(), (width - 7.0 * gap) / 8.0, h, false)); }
                emojis = emojis.push(row);
            }
            return Column::new().spacing(gap).push(tabs).push(Scrollable::new(emojis).height(height - h * 1.65 - gap * 2.0))
                .push(Row::new().spacing(gap).push(page_button("ABC", Page::Keyboard, w * 2.0, h))
                    .push(button("中 / EN", language(params), Length::Fill, h, false))
                    .push(key(params, "k_backspace", w * 2.0, h, unit))).into();
        }
        Page::Edit => {
            for actions in [vec![("全选", 'a' as u32, true, false), ("剪切", 'x' as u32, true, false), ("复制", 'c' as u32, true, false), ("粘贴", 'v' as u32, true, false)],
                vec![("撤销", 'z' as u32, true, false), ("↑", 0xff52, false, false), ("重做", 'z' as u32, true, true)],
                vec![("←", 0xff51, false, false), ("↓", 0xff54, false, false), ("→", 0xff53, false, false)],
                vec![("行首", 0xff50, false, false), ("行末", 0xff57, false, false), ("退格", 0xff08, false, false)]] {
                let mut row = Row::new().spacing(gap).height(h);
                for (label, sym, ctrl, shift) in actions { row = row.push(button(label, stroke(sym, ctrl, shift), Length::FillPortion(1), h, false)); }
                column = column.push(row);
            }
            return column.into();
        }
        Page::Settings => {
            let float = params.state.placement() == Placement::Float;
            let choices = [(if float { "停靠到底部" } else { "切为悬浮键盘" }, WindowManagerEvent::UpdatePlacement(if float { Placement::Dock } else { Placement::Float }).into()),
                ("文本编辑", LayoutEvent::FutoPage(Page::Edit).into()), ("更多键盘设置", LayoutEvent::ToggleSetting.into()),
                ("关于 FUTO / 支持原项目", LayoutEvent::FutoPage(Page::About).into())];
            for (label, action) in choices { column = column.push(button(label, action, Length::Fill, h, false)); }
            return column.into();
        }
        Page::Candidates => {
            let state = params.state.im().candidate_area_state();
            let mut grid = Column::new().spacing(gap);
            for (row_index, items) in state.candidate_list().chunks(3).enumerate() {
                let mut row = Row::new().spacing(gap);
                for (col_index, value) in items.iter().enumerate() {
                    let text = value.iter().map(|(s, _)| s.as_str()).collect::<String>();
                    row = row.push(button(text, ImEvent::SelectCandidate(state.cursor() + row_index * 3 + col_index).into(), Length::FillPortion(1), h, false));
                }
                grid = grid.push(row);
            }
            return Column::new().spacing(gap).push(Scrollable::new(grid).height(height - h - gap))
                .push(Row::new().push(button("‹ 上一页", ImEvent::PrevCandidates.into(), Length::Fill, h, false))
                    .push(button("下一页 ›", ImEvent::NextCandidates(state.cursor() + state.candidate_list().len()).into(), Length::Fill, h, false))).into();
        }
        Page::About => {
            return Column::new().spacing(gap).push(Text::new("FUTO Keyboard · Linux 移植").size(22).shaping(Shaping::Advanced))
                .push(Text::new("源自 FUTO Keyboard / LatinIME。非官方实验版本。\n原项目采用 FUTO Source First 许可；保留其版权和非商业条款。\n中文由水杉提供。语音、滑行与神经模型暂未移植。\n支持原项目：keyboard.futo.org").size(16).shaping(Shaping::Advanced))
                .push(page_button("返回键盘", Page::Keyboard, Length::Fill, h)).into();
        }
    }
    let available = width - gap * if normal { 5.0 } else { 4.0 };
    let mut bottom = Row::new().spacing(gap).height(h)
        .push(page_button(if page == Page::Keyboard { "?123" } else { "ABC" }, if page == Page::Keyboard { Page::Symbols } else { Page::Keyboard }, available * 0.15, h))
        .push(symbol_key(params, ',', available * 0.1, h, unit));
    if normal { bottom = bottom.push(page_button("☺", Page::Emoji, available * 0.1, h)); }
    bottom = bottom.push(key(params, "k_space", available * if normal { 0.4 } else { 0.5 }, h, unit));
    bottom = bottom.push(symbol_key(params, '.', available * 0.1, h, unit)).push(key(params, "k_enter", available * 0.15, h, unit));
    column.push(bottom).into()
}
