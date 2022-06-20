"""Implements functions for translation from lambda calculus to Python."""

import re

from dreamcoder.program import Abstraction, Application, Invented, Program
from lapspython.types import ParsedGrammar, ParsedProgram


class Translator:
    """Translate lambda programs to Python code."""

    def __init__(self, grammar: ParsedGrammar) -> None:
        """Init grammar used for translation and empty containers.

        :param grammar: Grammar used for translation
        :type grammar: lapspython.types.ParsedGrammar
        """
        self.grammar = grammar
        self.call_counts = {p: 0 for p in self.grammar.primitives}
        self.call_counts.update({i: 0 for i in self.grammar.invented})
        self.args: list = []
        self.dependencies: set = set()

    def translate(self, program: Program, name: str) -> ParsedProgram:
        """Init variables and call recursive translation function.

        :param program: Abstraction/Invented at any depth of lambda expression
        :type program: subclass of dreamcoder.program.Program
        :param name: Task/Function name
        :type name: string
        :returns: Translated program
        :rtype: ParsedProgram
        """
        for call in self.call_counts:
            self.call_counts[call] = 0
        self.args = []
        try:
            source = self._translate_program(program).strip()
        except (KeyError, ValueError):
            raise
        last_variable_assignments = re.findall(r'\w+ =', source)
        if len(last_variable_assignments) > 0:
            source = 'return'.join(source.split(last_variable_assignments[-1]))
        return ParsedProgram(name, source, self.args, self.dependencies)

    def _translate_program(self, program: Program) -> str:
        """Recursively parse nested lambda expressions under a given grammar.

        :param program: Abstraction/Invented at any depth of lambda expression
        :type program: subclass of dreamcoder.program.Program
        """
        if not isinstance(program, (Abstraction, Invented)):
            raise TypeError(f'Encountered unexpected type {type(program)}.')

        body = program.body

        if not isinstance(body, (Abstraction, Application)):
            raise TypeError(f'Encountered unexpected type {type(body)}.')

        if body.isAbstraction:
            return self._translate_program(program.body)

        try:
            code, f_parsed, x_args = self._translate_application(body)
        except ValueError:
            raise
        self.call_counts[f_parsed.handle] += 1
        name = f'{f_parsed.name}_{self.call_counts[f_parsed.handle]}'

        # Handle invented primitives
        if not program.isAbstraction:
            for i in range(len(f_parsed.args) - len(x_args)):
                handle = str(program)
                try:
                    name = self.grammar.invented[handle].name
                except KeyError:
                    raise
                x_args.append(f'{name}_{i + 1}')
                self.args.append(f'{name}_{i + 1}')

        code += f_parsed.resolve_variables(x_args, name) + '\n'
        return code

    def _translate_application(self, application: Application) -> tuple:
        """Parse function and argument of application object.

        :param program: Application object f(x)
        :type program: dreamcoder.type.Application
        :returns: (code, ParsedPrimitive, args) tuple
        :rtype: tuple
        """
        code = ''

        x = application.x
        if x.isIndex:
            x_args = [f'arg{x.i}']
            self.args.append(x_args[0])
        elif x.isPrimitive:
            if isinstance(x.value, str):
                x_args = [f"'{x.value}'"]
            else:
                raise TypeError(f'Encountered unexpected type {type(x)}.')
        elif x.isApplication:
            x_code, x_parsed, x_args = self._translate_application(x)
            if x_parsed is not None:
                self.call_counts[x_parsed.handle] += 1
                name = f'{x_parsed.name}_{self.call_counts[x_parsed.handle]}'
                x_parsed_resolved = x_parsed.resolve_variables(x_args, name)
                code += x_code + x_parsed_resolved + '\n'
                x_args = [name]
        elif x.isAbstraction:
            if x.body.isIndex:
                lambda_body = f'arg{x.body.i}'
            else:
                lambda_body = str(x.body)
            x_args = [f'lambda lx: {lambda_body}']
        else:
            raise TypeError(f'Encountered unexpected type {type(x)}.')

        f = application.f
        if f.isPrimitive:
            f_parsed = self.grammar.primitives[f.name].resolve_lambdas()
            self.dependencies.update(f_parsed.dependencies)
        elif f.isApplication:
            f_code, f_parsed, f_args = self._translate_application(f)
            x_args = f_args + x_args
        elif f.isIndex:
            f_parsed = None
            x_args = [f'arg{f.i}'] + x_args
        elif f.isInvented:
            handle = str(f)
            self.call_counts[handle] += 1
            f_parsed = self.grammar.invented[handle]
            if f_parsed.source == '':
                raise ValueError('Invented primitive has no translation')
            self.dependencies.update(f_parsed.dependencies)
            self.dependencies.add(f_parsed.source)
            name = f'{f_parsed.name}_{self.call_counts[handle]}'
            code += f_parsed.resolve_variables(x_args, name) + '\n'
        else:
            raise TypeError(f'Encountered unexpected type {type(f)}.')

        return code, f_parsed, x_args
