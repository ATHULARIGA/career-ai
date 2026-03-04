# Future Implementations

## 1. Interactive Learning Path
- **Node Expansion**: Click on a child node (e.g., "Python") to trigger a secondary AI call that generates a sub-roadmap for that specific skill.
- **Resource Linking**: Automatically attach curated learning resources (YouTube, Coursera, Documentation) to each node as tooltips.

## 2. Progress Tracking
- **Checklist Mode**: Allow users to "check off" nodes they have mastered.
- **Persistence**: Save user roadmaps to the database so they can return to them later and track their journey.

## 3. Dynamic Filtering
- **Difficulty Toggle**: Add a slider to switch between "Beginner", "Intermediate", and "Advanced" views of the same roadmap.
- **Role Comparison**: Overlay two roadmaps (e.g., "Data Scientist" vs "AI Engineer") to see overlapping core skills.

## 4. Enhanced Visualization
- **Export Options**: Allow users to download their roadmap as a high-quality PNG or SVG for sharing.
- **Auto-Layout Optimization**: Use D3's `forceCollide` more aggressively for very large maps to ensure zero text overlap.

## 5. Resume Alignment
- **Gap Analysis**: Compare the generated roadmap against the user's uploaded resume and highlight nodes they are missing in red.
