"use strict";

const state = { spec: null, selected: null, query: "" };
const groups = [
  ["tools", "Tools", "tool"],
  ["resources", "Resources", "resource"],
  ["resourceTemplates", "Resource templates", "resource template"],
  ["prompts", "Prompts", "prompt"],
];

const byId = (id) => document.getElementById(id);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function schemaType(schema) {
  if (!schema) return "unknown";
  if (schema.$ref) return schema.$ref.split("/").pop();
  if (schema.enum) return `enum(${schema.enum.join(", ")})`;
  if (schema.type) return schema.type;
  if (schema.anyOf) return schema.anyOf.map(schemaType).join(" | ");
  if (schema.items) return `array<${schemaType(schema.items)}>`;
  return "object";
}

function appendDescription(parent, text) {
  if (!text) return;
  parent.append(element("p", "description", text));
}

function schemaTable(schema) {
  const properties = schema.properties || {};
  if (!Object.keys(properties).length) return null;
  const wrapper = element("div", "schema-summary");
  const table = element("table");
  const head = document.createElement("thead");
  const body = document.createElement("tbody");
  const header = document.createElement("tr");
  ["필드", "타입", "필수", "기본값", "설명"].forEach((name) => header.append(element("th", "", name)));
  head.append(header);
  const required = new Set(schema.required || []);

  Object.entries(properties).forEach(([name, property]) => {
    const row = document.createElement("tr");
    row.append(element("td", "", name));
    row.append(element("td", "type", schemaType(property)));
    row.append(element("td", required.has(name) ? "required" : "optional", required.has(name) ? "required" : "optional"));
    row.append(element("td", "", Object.hasOwn(property, "default") ? JSON.stringify(property.default) : "—"));
    row.append(element("td", "", property.description || "—"));
    body.append(row);
  });
  table.append(head, body);
  wrapper.append(table);
  return wrapper;
}

function renderDefinitions(schema) {
  const definitions = schema.$defs || {};
  if (!Object.keys(definitions).length) return null;
  const details = element("details");
  details.append(element("summary", "", `참조 타입 ${Object.keys(definitions).length}개`));
  const container = element("div", "definitions");
  Object.entries(definitions).forEach(([name, definition]) => {
    const card = element("section", "definition");
    card.append(element("h3", "", name));
    appendDescription(card, definition.description);
    const table = schemaTable(definition);
    if (table) card.append(table);
    container.append(card);
  });
  details.append(container);
  return details;
}

function renderSchema(title, schema) {
  const section = element("section", "schema-section");
  const heading = element("div", "schema-heading");
  heading.append(element("h3", "", title), element("code", "", schema.title || "JSON Schema"));
  section.append(heading);
  appendDescription(section, schema.description);
  const table = schemaTable(schema);
  if (table) section.append(table);
  const definitions = renderDefinitions(schema);
  if (definitions) section.append(definitions);
  const details = element("details");
  details.append(element("summary", "", "전체 JSON Schema 보기"));
  details.append(element("pre", "", JSON.stringify(schema, null, 2)));
  section.append(details);
  return section;
}

function itemName(kind, item) {
  return item.name || item.uri || item.uriTemplate || "unnamed";
}

function renderDetail(kind, item) {
  const detail = byId("detail");
  detail.replaceChildren();
  detail.append(element("p", "kind", kind));
  detail.append(element("h2", "", item.title || itemName(kind, item)));
  const identifier = item.name || item.uri || item.uriTemplate;
  if (identifier) detail.append(element("p", "meta", identifier));
  appendDescription(detail, item.description);

  if (kind === "tool") {
    detail.append(renderSchema("입력 스키마", item.inputSchema || {}));
    if (item.outputSchema) detail.append(renderSchema("출력 스키마", item.outputSchema));
  } else if (kind === "resource" || kind === "resource template") {
    const metadata = element("section", "schema-section");
    const heading = element("div", "schema-heading");
    heading.append(element("h3", "", "리소스 메타데이터"));
    metadata.append(heading);
    const table = element("div", "schema-summary");
    table.append(element("p", "description", `MIME type: ${item.mimeType || "지정되지 않음"}`));
    metadata.append(table);
    detail.append(metadata);
  } else if (kind === "prompt" && item.arguments) {
    detail.append(renderSchema("프롬프트 인자", { properties: Object.fromEntries(item.arguments.map((arg) => [arg.name, arg])), required: item.arguments.filter((arg) => arg.required).map((arg) => arg.name) }));
  }
}

function matches(item) {
  if (!state.query) return true;
  const value = `${itemName("", item)} ${item.title || ""} ${item.description || ""}`.toLowerCase();
  return value.includes(state.query.toLowerCase());
}

function renderNavigation() {
  const navigation = byId("navigation");
  navigation.replaceChildren();
  groups.forEach(([key, label, kind]) => {
    const items = (state.spec[key] || []).filter(matches);
    if (!items.length && state.query) return;
    const group = element("section", "nav-group");
    group.append(element("p", "nav-group-title", `${label} (${items.length})`));
    if (!items.length) {
      group.append(element("p", "nav-empty", "등록된 항목이 없습니다."));
    }
    items.forEach((item) => {
      const button = element("button", "nav-item", item.title || itemName(kind, item));
      button.type = "button";
      const identity = `${kind}:${itemName(kind, item)}`;
      if (state.selected === identity) button.classList.add("active");
      button.addEventListener("click", () => {
        state.selected = identity;
        renderNavigation();
        renderDetail(kind, item);
        history.replaceState(null, "", `#${encodeURIComponent(identity)}`);
      });
      group.append(button);
    });
    navigation.append(group);
  });
}

function renderSummary() {
  const template = byId("count-template");
  const counts = byId("counts");
  counts.replaceChildren();
  groups.forEach(([key, label]) => {
    const fragment = template.content.cloneNode(true);
    fragment.querySelector("strong").textContent = String((state.spec[key] || []).length);
    fragment.querySelector("span").textContent = label;
    counts.append(fragment);
  });
}

function selectInitialItem() {
  const hash = decodeURIComponent(location.hash.slice(1));
  for (const [key, , kind] of groups) {
    for (const item of state.spec[key] || []) {
      const identity = `${kind}:${itemName(kind, item)}`;
      if (identity === hash || !state.selected) {
        state.selected = identity;
        renderDetail(kind, item);
        if (identity === hash) return;
      }
    }
  }
}

async function start() {
  try {
    const response = await fetch("mcp-spec.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`명세 요청 실패 (${response.status})`);
    state.spec = await response.json();
    byId("server-name").textContent = state.spec.server?.name || "MCP 문서";
    byId("format-version").textContent = `${state.spec.format || "MCP"} v${state.spec.formatVersion || "?"}`;
    renderSummary();
    selectInitialItem();
    renderNavigation();
    byId("loading").hidden = true;
    byId("document").hidden = false;
    byId("search").addEventListener("input", (event) => {
      state.query = event.target.value.trim();
      renderNavigation();
    });
  } catch (error) {
    byId("loading").hidden = true;
    const errorBox = byId("error");
    errorBox.textContent = `문서를 표시하지 못했습니다: ${error.message}`;
    errorBox.hidden = false;
  }
}

start();
