"""Generate a review-only generic patch against the immutable host objects."""
from pathlib import Path
import difflib
from env import ROOT
from contracts import capture
p=capture();patch=[]
for file in ['src/renderer/src/raycast-api/list-runtime.tsx','src/renderer/ExtensionRuntimeView.tsx','src/shared/extensionRuntime.ts']:
 s=(p/('host-'+Path(file).name)).read_text();new=s
 if file.endswith('list-runtime.tsx'):
  new=new.replace("if (typeof root.props?.searchText === 'string') {\n      setQuery(root.props.searchText)","if (!hasServerSearch && typeof root.props?.searchText === 'string') {\n      setQuery(root.props.searchText)").replace('}, [root.props?.searchText])','}, [hasServerSearch, root.props?.searchText])')
  new=new.replace("    if (query === lastSentQuery.current) return","    if (hasServerSearch || query === lastSentQuery.current) return").replace('}, [query, onSearchTextChanged])','}, [hasServerSearch, query, onSearchTextChanged])')
  new=new.replace('''                  setQuery(event.target.value)
                  setSelected(0)''','''                  const next = event.target.value
                  setQuery(next)
                  setSelected(0)
                  // Fence server replies at input time, before any debounce window.
                  if (hasServerSearch && next !== lastSentQuery.current) {
                    lastSentQuery.current = next
                    void onSearchTextChanged(next)
                  }''')
  # Preserve generic native row semantics already emitted by V1 adapters.
  new=new.replace("    tintColor?: unknown\n", "    tintColor?: unknown\n    tooltip?: unknown\n",1)
  new=new.replace("icon?: unknown }>\n", "icon?: unknown; tooltip?: unknown }>\n",1)
  new=new.replace("tintColor?: unknown }\n", "tintColor?: unknown; tooltip?: unknown }\n",1)
  new=new.replace("return { source: icon.source, tintColor: icon.tintColor }", "return { source: icon.source, tintColor: icon.tintColor, tooltip: icon.tooltip }")
  new=new.replace("      icon: entry.icon,", "      icon: entry.icon,\n      tooltip: entry.tooltip,")
  new=new.replace("title={row.title} tintColor={row.icon.tintColor}", "title={textValue(row.icon.tooltip) || row.title} tintColor={row.icon.tintColor}")
  new=new.replace("      aria-hidden=\"true\"\n    >\n      <svg", "      title={title}\n    >\n      <svg",1)
  new=new.replace("{label.includes('check') ? (", "{label === 'star' ? (\n          <path d=\"m12 3 2.78 5.63 6.22.9-4.5 4.39 1.06 6.2L12 17.2l-5.56 2.92 1.06-6.2L3 9.53l6.22-.9L12 3Z\" />\n        ) : label === 'rotateanticlockwise' ? (\n          <>\n            <path d=\"M3 10a9 9 0 1 1 2.4 8M3 4v6h6\" />\n          </>\n        ) : label.includes('check') ? (")
  new=new.replace("            : 'bg-white/10 text-ink-2'", "            : tagColor.includes('yellow')\n              ? 'bg-yellow-500/20 text-yellow-300'\n              : tagColor.includes('magenta')\n                ? 'bg-fuchsia-500/20 text-fuchsia-300'\n                : 'bg-white/10 text-ink-2'")
  new=new.replace("  const value = accessoryText(accessory)", "  const value = accessoryText(accessory)")
  accessory=new.index('function Accessory(');pos=new.index('    <span\n',accessory);new=new[:pos]+new[pos:].replace('    <span\n','    <span\n      title={textValue(accessory.tooltip) || undefined}\n',1)
  new=new.replace("    : hasQuery\n      ? 'No matching applications'\n      : emptyView?.title || 'No list items'", "    : emptyView?.title || (hasQuery ? 'No matching applications' : 'No list items')")
  new=new.replace("    : hasQuery\n      ? 'Try a different app name or keyword.'\n      : emptyView?.description || ''", "    : emptyView?.description || (hasQuery ? 'Try a different app name or keyword.' : '')")
 elif file.endswith('extensionRuntime.ts'):
  for name in ['ExtensionInvokeActionResult','ExtensionSearchTextChangedResult']:
   new=new.replace('export type '+name+' =\n',"export type "+name+" =\n  | { ok: true; mode: 'unchanged' }\n")
 else:
  start=new.index('  const handleSearchTextChanged = useCallback(');end=new.index('  const handleLoadMore',start)
  new=new[:start]+'''  const handleSearchTextChanged = useCallback(
    async (searchText: string) => {
      const requestSeq = ++searchRequestSeq.current
      const isCurrent = (): boolean =>
        requestSeq === searchRequestSeq.current && currentSession.current === sessionOwner
      try {
        const result = await window.tezbar.extensionSearchTextChanged({
          sessionId: state.sessionId,
          searchText,
        })
        if (!isCurrent()) return
        if (!result.ok) {
          setError(result.message)
          return
        }
        if (result.mode === 'unchanged') return
        if (result.mode === 'view' &&
          (result.sessionId !== state.sessionId || result.generation !== state.generation)) return
        setError(null)
        if (result.mode === 'no-view') {
          setState((prev) => ({ ...prev, message: result.message }))
          return
        }
        setState(fromRunResult(result))
      } catch (error) {
        if (isCurrent()) setError(error instanceof Error ? error.message : String(error))
      }
    },
    [state.sessionId, state.generation, sessionOwner]
  )

'''+new[end:]
  new=new.replace('''          <ExtensionRuntimeSurface
            sessionId''','''          <ExtensionRuntimeSurface
            key={sessionOwner}
            sessionId''')
  # Refresh/load-more/action replies own the search epoch as well as session.
  new=new.replace("      refresh: async () => {\n        try", "      refresh: async () => {\n        const requestSeq = searchRequestSeq.current\n        try").replace("          if (cancelled || (result.ok", "          if (requestSeq !== searchRequestSeq.current || cancelled || (result.ok")
  new=new.replace("          if (!cancelled) setError(error instanceof Error ? error.message : String(error))", "          if (!cancelled && requestSeq === searchRequestSeq.current) setError(error instanceof Error ? error.message : String(error))")
  new=new.replace("    const result = await window.tezbar.extensionLoadMore", "    const requestSeq = searchRequestSeq.current\n    const result = await window.tezbar.extensionLoadMore").replace("    if (currentSession.current !== sessionOwner) return", "    if (currentSession.current !== sessionOwner || requestSeq !== searchRequestSeq.current) return")
  begin=new.index('            onInvokeAction={async (actionId, formValues) => {');end=new.index('\n            }}',begin)
  body=new[begin:end]
  body=body.replace('              setError(null)', '              const requestSeq = searchRequestSeq.current',1)
  body=body.replace('              const result = await', '              try {\n              const result = await',1)
  body=body.replace('              if (currentSession.current !== sessionOwner) return', '              if (currentSession.current !== sessionOwner || requestSeq !== searchRequestSeq.current) return')
  body=body.replace('              const effectNoticeValue', "              if (result.mode === 'unchanged') return\n              setError(null)\n              if (result.mode === 'view' && (result.sessionId !== state.sessionId || result.generation !== state.generation)) return\n              const effectNoticeValue")
  body+='\n              } catch (error) {\n                if (currentSession.current !== sessionOwner || requestSeq !== searchRequestSeq.current) return\n                const message = error instanceof Error ? error.message : String(error)\n                setError(message)\n                showActionFailure(message)\n              }'
  new=new[:begin]+body+new[end:]
 assert new!=s
 (p/('patched-'+Path(file).name)).write_text(new)
 patch.extend(difflib.unified_diff(s.splitlines(True),new.splitlines(True),fromfile='a/'+file,tofile='b/'+file))
(ROOT/'host-prerequisite.patch').write_text(''.join(patch));print('UNAPPLIED host prerequisite patch generated')
