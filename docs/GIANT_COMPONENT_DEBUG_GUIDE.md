# Giant Component Filter - Debugging Guide

## Problem
Giant component filter checkbox doesn't appear to do anything when toggled.

## Debugging Steps Added

### 1. Enhanced Console Logging

The following debug logs were added to help diagnose the issue:

**When filter is toggled:**
```
Giant component filter: ON (or OFF)
```

**When applyFilters() runs:**
```
Applying filters: { nodeTypes: [], search: '', giantComponentOnly: true }
Starting with X nodes
Filtered edges: Y
Extracting giant component...
Found N connected component(s)
Giant component: X nodes (XX.X% of network)
Other components: [sizes] nodes
After giant component: X nodes, Y edges
Final graph: X nodes, Y edges
```

### 2. How to Test

1. **Open browser console** (F12 or right-click → Inspect → Console)

2. **Load a network visualization**

3. **Toggle the giant component filter checkbox**

4. **Watch the console output**

### 3. What to Look For

#### Case 1: Network is Fully Connected
If you see:
```
Found 1 connected component(s)
Giant component: 100 nodes (100.0% of network)
```
This means the network has only ONE component - all nodes are connected. The filter won't change anything because there's no smaller components to filter out.

**Solution**: This is expected behavior. The giant component IS the entire network.

#### Case 2: Network Has Multiple Components
If you see:
```
Found 3 connected component(s)
Giant component: 85 nodes (85.0% of network)
Other components: 10, 5 nodes
After giant component: 85 nodes, 120 edges
```
You should see nodes disappear (the 10 and 5 node components are hidden).

#### Case 3: No Output at All
If you don't see ANY console output when toggling:
- The checkbox event handler isn't firing
- Check Alpine.js is loaded
- Check the `toggleGiantComponent()` method is being called

#### Case 4: "No rawData available"
If you see this warning:
```
No rawData available for filtering
```
The network hasn't loaded yet or failed to load. Check the network load request.

### 4. Manual Testing Checklist

- [ ] Open network visualization page
- [ ] Open browser console (F12)
- [ ] Toggle giant component checkbox ON
- [ ] Verify console shows "Giant component filter: ON"
- [ ] Verify console shows filtering output
- [ ] Check if node count changes in the UI
- [ ] Toggle giant component checkbox OFF
- [ ] Verify console shows "Giant component filter: OFF"
- [ ] Verify all nodes reappear

### 5. Test with Disconnected Network

To properly test the giant component filter, you need a network with **multiple components**.

**Creating a test network:**
- Search for unrelated terms that won't have overlapping websites
- Or manually create a test GEXF file with disconnected nodes

Example test GEXF:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft">
  <graph defaultedgetype="undirected">
    <nodes>
      <!-- Component 1: A-B-C (giant) -->
      <node id="A" label="Node A"/>
      <node id="B" label="Node B"/>
      <node id="C" label="Node C"/>
      <!-- Component 2: D-E -->
      <node id="D" label="Node D"/>
      <node id="E" label="Node E"/>
      <!-- Component 3: F (isolated) -->
      <node id="F" label="Node F"/>
    </nodes>
    <edges>
      <edge source="A" target="B"/>
      <edge source="B" target="C"/>
      <edge source="D" target="E"/>
    </edges>
  </graph>
</gexf>
```

**Expected behavior:**
- Without filter: 6 nodes
- With filter: 3 nodes (A-B-C only)
- Console: "Found 3 connected component(s)"

### 6. Common Issues

#### Issue: Filter works but no visible change
**Cause**: Network is fully connected (only 1 component)
**Solution**: Normal behavior - try different network

#### Issue: No console output
**Cause**: JavaScript not loading or Alpine.js error
**Check**:
- Browser console for errors
- Network tab for 404s
- Alpine.js loaded before page

#### Issue: Console shows filtering but graph doesn't update
**Cause**: `renderer.refresh()` not working
**Check**:
- Sigma.js renderer initialized
- Graph cleared before rebuild
- No JavaScript errors

#### Issue: Stats don't update
**Cause**: `updateStats()` not called after filter
**Solution**: Already wired in `toggleGiantComponent()`

### 7. Alternative: Test from Console

You can manually test the filter from the browser console:

```javascript
// Get the Alpine.js component
const vizComponent = Alpine.$data(document.querySelector('[x-data]'));

// Check current state
console.log('Current filters:', vizComponent.visualizer.filters);

// Manually enable giant component filter
vizComponent.visualizer.setGiantComponentFilter(true);

// Check if it worked
console.log('After enable:', vizComponent.visualizer.filters);

// Manually disable
vizComponent.visualizer.setGiantComponentFilter(false);
```

### 8. Network Statistics

The stats panel should update when filter is applied:
- **Nodes**: Should decrease (unless fully connected)
- **Edges**: Should decrease proportionally
- **Density**: May increase or decrease
- **Avg. Degree**: Usually increases (giant component is denser)

### 9. Next Steps

1. **Try the filter** with debug logging enabled
2. **Copy console output** and share if issue persists
3. **Check network structure** - is it fully connected?
4. **Test with known disconnected network**

### 10. Expected Console Output Example

```
Giant component filter: ON
Applying filters: { nodeTypes: [], search: '', giantComponentOnly: true }
Starting with 100 nodes
Filtered edges: 150
Extracting giant component...
Found 4 connected component(s)
Giant component: 85 nodes (85.0% of network)
Other components: 8, 5, 2 nodes
After giant component: 85 nodes, 138 edges
Final graph: 85 nodes, 138 edges
```

If you see this output but the graph doesn't change visually, there may be a rendering issue. Try:
- Clicking "Fit to view" button
- Toggling layout on/off
- Zooming in/out

---

## Summary

The giant component filter is now instrumented with extensive debug logging. When you toggle it, you should see detailed console output explaining:
1. Whether the filter was enabled/disabled
2. How many components were found
3. What percentage is the giant component
4. How many nodes/edges after filtering

If nothing appears to change, check the console - you may have a fully connected network (only 1 component).
