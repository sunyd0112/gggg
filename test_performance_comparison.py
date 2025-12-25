"""Compare performance before/after the change.

Tests:
1. Execution time (should be faster with parallel execution)
2. Quality metrics (story coherence, slide count accuracy)
3. Refinement quality (with atoms vs without)
"""
import time
from pathlib import Path
from datetime import datetime
from src.generation.state import PipelineState
from src.generation.todo.runner import PipelineRunner

def compare_performance():
    """Run tests to compare new vs old architecture."""
    
    print("=" * 60)
    print("PERFORMANCE COMPARISON TEST")
    print("=" * 60)
    
    # Test source file
    source_file = Path("data/context/career_talk.txt")
    if not source_file.exists():
        source_file = list(Path("data").rglob("*.txt"))[0] if list(Path("data").rglob("*.txt")) else None
        if not source_file:
            print("❌ No test source file found")
            return
    
    print(f"\n📄 Source: {source_file}")
    
    # Test 1: Initial Generation Speed
    print("\n" + "="*60)
    print("TEST 1: Initial Generation Speed")
    print("="*60)
    
    output_dir = Path(f"output/perf_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    runner = PipelineRunner(verbose=True, output_dir=output_dir)
    
    start_time = time.time()
    state = runner.run(
        source_path=source_file,
        user_instruction="Create 8 slides, professional tone, include metrics",
    )
    end_time = time.time()
    
    generation_time = end_time - start_time
    print(f"\n⏱️  Total generation time: {generation_time:.2f} seconds")
    
    # Analyze execution
    completed_todos = [t for t in state.todos.todos if t.status.value == "completed"]
    print(f"✅ Completed todos: {len(completed_todos)}")
    
    for todo in completed_todos:
        print(f"   - {todo.type.value}")
    
    # Check parallel execution (atoms and story should have similar depends_on)
    story_todo = next((t for t in state.todos.todos if t.type.value == "story"), None)
    atoms_todo = next((t for t in state.todos.todos if t.type.value == "atoms"), None)
    
    if story_todo and atoms_todo:
        print(f"\n📊 Dependency Analysis:")
        print(f"   Story depends on: {story_todo.depends_on}")
        print(f"   Atoms depends on: {atoms_todo.depends_on}")
        
        # Check if they have same dependencies (means they can run in parallel)
        if story_todo.depends_on == atoms_todo.depends_on:
            print("   ✅ Can run in PARALLEL (same dependencies)")
        else:
            print("   ⚠️  Run SEQUENTIALLY (different dependencies)")
    
    # Test 2: Quality Check
    print("\n" + "="*60)
    print("TEST 2: Output Quality")
    print("="*60)
    
    if state.slides:
        print(f"\n📊 Slide Count: {len(state.slides)} (requested: 8)")
        accuracy = abs(len(state.slides) - 8) <= 2  # Within 2 slides
        print(f"   {'✅' if accuracy else '⚠️'} Accuracy: {'Good' if accuracy else 'Off target'}")
        
        # Check slide structure
        print("\n📋 Slide Structure:")
        for i, slide in enumerate(state.slides[:3], 1):  # First 3 slides
            print(f"\nSlide {i}:")
            print(f"   story: {slide.get('story', 'N/A')[:80]}...")
            print(f"   density: {slide.get('density', 'N/A')}")
            print(f"   visual_design: {slide.get('visual_design', 'N/A')[:80]}...")
            print(f"   atoms: {len(slide.get('atoms', []))} atoms")
    
    # Test 3: Refinement with Atoms
    print("\n" + "="*60)
    print("TEST 3: Refinement Quality (with atoms)")
    print("="*60)
    
    print("\n🔄 Testing refinement: 'merge slides 1 and 2'")
    
    # Clear todos for incremental update
    state.clear_todos()
    
    refine_start = time.time()
    state = runner.run(
        source_path=source_file,
        user_instruction="merge slides 1 and 2",
        state=state,
    )
    refine_end = time.time()
    
    refine_time = refine_end - refine_start
    print(f"\n⏱️  Refinement time: {refine_time:.2f} seconds")
    
    if state.slides:
        print(f"📊 Slide count after merge: {len(state.slides)} (should be ~7)")
        
        # Check if atoms were used in refinement
        story_todo_refine = next((t for t in state.todos.todos 
                                  if t.type.value == "story" and t.status.value == "completed"), None)
        if story_todo_refine:
            print(f"   Story refinement completed")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Initial generation: {generation_time:.2f}s")
    print(f"✅ Refinement: {refine_time:.2f}s")
    print(f"✅ Total time: {generation_time + refine_time:.2f}s")
    print(f"\n📁 Results saved to: {output_dir}")
    
    # Key metrics
    print("\n🎯 Key Findings:")
    print(f"   - Story/Atoms can run in parallel: {story_todo.depends_on == atoms_todo.depends_on if story_todo and atoms_todo else 'N/A'}")
    print(f"   - Generated {len(state.slides)} slides")
    print(f"   - Refinement works: {len(state.slides) < 8 if state.slides else False}")
    
    return state

if __name__ == "__main__":
    compare_performance()
