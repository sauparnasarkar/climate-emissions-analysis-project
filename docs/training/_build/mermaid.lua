function CodeBlock(el)
  if el.classes:includes('mermaid') then
    return pandoc.RawBlock('html', '<pre class="mermaid">\n' .. el.text:gsub('&','&amp;'):gsub('<br/>','<br/>') .. '\n</pre>')
  end
end
