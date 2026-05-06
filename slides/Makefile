DECK := deck.md
THEME := riprap.css
MARP := marp $(DECK) --theme $(THEME) --allow-local-files --html

.PHONY: all pdf html pptx clean

all: pdf html pptx

pdf:
	$(MARP) --pdf  --output deck.pdf

html:
	$(MARP) --output deck.html

pptx:
	$(MARP) --pptx --output deck.pptx

clean:
	rm -f deck.pdf deck.html deck.pptx
