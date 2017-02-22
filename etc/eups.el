;;
;; GNU-lisp functions for editing eups table files
;;
;; The following should be put in your .emacs file to automatically
;; load these functions when editing table files
;;
;;(setq auto-mode-alist
;;      (cons (cons "\\.table$" 'eups-mode) auto-mode-alist))
;;(autoload 'eups-mode "~rhl/eups/etc/eups.el" nil t)
;;
;; Alternatively, if the first line of a file contains the string
;;		-*-eups-*-
;; emacs will load eups-mode
;;
;; This file is based on code in GNU Emacs, and is accordingly covered
;; by the GNU General Public License: you can redistribute it and/or modify
;; it under the terms of the GNU General Public License as published by
;; the Free Software Foundation; either version 1, or (at your option)
;; any later version.
;;
;; You should have received a copy of the GNU General Public License
;; along with GNU Emacs; see the file COPYING.  If not, write to
;; the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
;;
;; syntax colouring
;;
(defvar
  eups-font-lock-keywords
   '(
     ("\\<\\(else\\|if\\|not\\|print\\)\\>" (1 font-lock-keyword-face))
     ("\\<\\(std\\(err\\|info\\|ok\\|warn\\)\\)\\>" (1 font-lock-variable-name-face))
     ;; relatively unusual commands
     ("\\<\\(envAppend\\|setupOptional\\|unsetup\\(Required\\|Optional\\)\\)\\>" (1 font-lock-constant-face))
     ;; common commands
     ("\\<\\(addAlias\\|declareOptions\\|env\\(Set\\|Unset\\|Prepend\\)\\|setupRequired\\)\\>" (1 font-lock-function-name-face))
     ;; deprecated synonyms
     ("\\<\\(path\\(Append\\|Prepend\\|Remove\\|Set\\|Unset\\)\\|prodDir\\|setupenv\\|\\(un\\)?setenv\\|sourceRequired\\)\\>" (1 font-lock-keyword-face))
     )
"*Keyword highlighting specification for `eups-mode'.")

;;
;; Syntax colouring for comments too
;;
(defvar eups-syntax-table nil "Syntax table for `eups-mode'.")
(setq eups-syntax-table
      (let ((synTable (make-syntax-table)))

        ;; Comments from # to end of line
        (modify-syntax-entry ?# "< b" synTable)
        (modify-syntax-entry ?\n "> b" synTable)

        synTable))
;;
(define-derived-mode eups-mode c-mode "Eups"
  "Major mode for editing eups code.

Turning on eups mode calls the value of the variable eups-mode-hook
with no args, if it is non-nil.
\\{eups-mode-map}"
  ;;(interactive "p")

  (set-syntax-table eups-syntax-table)

  (setq comment-start "# ")
  (setq comment-end "")

  (make-local-variable 'require-final-newline)
  (setq require-final-newline t)

  (setq font-lock-defaults '(eups-font-lock-keywords))
  )

(add-hook 'eups-mode-hook '(lambda ()
			     (interactive)
			     (setq font-lock-keywords-case-fold-search t)
			     ))

(provide 'eups-mode)
