"""Few-shot ScratchScript examples for the LLM system prompt."""

FEW_SHOT_EXAMPLES = '''
### Example 1: Simple — Cat walks and meows

User: "Make a cat that walks back and forth and meows when clicked"

```
project
  sprite Cat
    costumes "cat-a", "cat-b"
    sounds "Meow"
    position 0, 0
    size 100

    script
      when flag clicked
        forever
          move 10
          next costume
          wait 0.2
          if on edge bounce

    script
      when this sprite clicked
        play sound until done "Meow"
        say "Meow!" 2
```

### Example 2: Medium — Score counter game

User: "Make a game where you click a ball to score points, with a timer that counts down from 30"

```
project
  variable score = 0
  variable timeLeft = 30

  sprite Ball
    costumes "ball-a"
    position 0, 0
    size 80

    script
      when flag clicked
        set score to 0
        set timeLeft to 30
        show variable score
        show variable timeLeft
        forever
          go to x y (pick random -200 200) (pick random -150 150)
          wait 1

    script
      when flag clicked
        repeat 30
          wait 1
          change timeLeft by -1
        stop all

    script
      when this sprite clicked
        change score by 1
        start sound "Pop"
```

### Example 3: Complex — Simple chase game

User: "Make a game where a cat chases the mouse pointer and a dog chases the cat. If the dog catches the cat, game over."

```
project
  variable gameOver = 0
  backdrops "Blue Sky"

  sprite Cat
    costumes "cat-a", "cat-b"
    position 0, 0
    size 80

    script
      when flag clicked
        set gameOver to 0
        forever
          point towards "mouse-pointer"
          move 5
          next costume
          wait 0.1
          if touching "Dog"
            set gameOver to 1
            say "Game Over!" 2
            stop all

  sprite Dog
    costumes "dog-a", "dog-b"
    position -200, -100
    size 80

    script
      when flag clicked
        forever
          point towards "Cat"
          move 3
          next costume
          wait 0.1
'''
